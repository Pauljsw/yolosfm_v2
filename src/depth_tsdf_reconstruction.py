"""
Phase 1: Depth-only Ground Truth Reconstruction
Generates absolute-scale 3D model from depth images using TSDF fusion.
This serves as the ground truth for SFM scale alignment.
"""
import numpy as np
import cv2
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import json

logger = logging.getLogger(__name__)

try:
    import open3d as o3d
    HAS_OPEN3D = True
except ImportError:
    logger.warning("Open3D not installed. TSDF reconstruction unavailable.")
    HAS_OPEN3D = False


class DepthTSDFReconstructor:
    """TSDF-based depth reconstruction for ground truth generation"""

    def __init__(
        self,
        voxel_length: float = 0.01,  # 1cm voxels
        sdf_trunc: float = 0.04,     # 4cm truncation
        depth_scale: float = 1000.0,  # mm to m
        depth_trunc: float = 10.0,    # max depth 10m
    ):
        """
        Initialize TSDF reconstructor.

        Args:
            voxel_length: Voxel size in meters
            sdf_trunc: SDF truncation distance in meters
            depth_scale: Depth scale (1000 for mm->m, 1 for m->m)
            depth_trunc: Maximum valid depth in meters
        """
        if not HAS_OPEN3D:
            raise ImportError("Open3D is required for TSDF reconstruction")

        self.voxel_length = voxel_length
        self.sdf_trunc = sdf_trunc
        self.depth_scale = depth_scale
        self.depth_trunc = depth_trunc

        # Create TSDF volume
        self.volume = o3d.pipelines.integration.ScalableTSDFVolume(
            voxel_length=voxel_length,
            sdf_trunc=sdf_trunc,
            color_type=o3d.pipelines.integration.TSDFVolumeColorType.RGB8
        )

        self.trajectory = []  # Store poses for later use

    def integrate_frame(
        self,
        rgb_img: np.ndarray,
        depth_img: np.ndarray,
        K: np.ndarray,
        pose: np.ndarray,
        frame_id: str
    ):
        """
        Integrate one RGB-D frame into TSDF volume.

        Args:
            rgb_img: RGB image (H, W, 3), uint8
            depth_img: Depth image (H, W), float32 in meters
            K: Camera intrinsic matrix (3, 3)
            pose: Camera pose (4, 4), world-to-camera transform
            frame_id: Frame identifier
        """
        h, w = depth_img.shape

        # Convert depth to Open3D format
        # Open3D expects depth in depth_scale units (e.g., mm if scale=1000)
        depth_o3d = (depth_img * self.depth_scale).astype(np.uint16)

        # Create Open3D images
        color_o3d = o3d.geometry.Image(rgb_img)
        depth_o3d = o3d.geometry.Image(depth_o3d)

        # Create RGBD image
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d,
            depth_o3d,
            depth_scale=self.depth_scale,
            depth_trunc=self.depth_trunc,
            convert_rgb_to_intensity=False
        )

        # Create intrinsic
        intrinsic = o3d.camera.PinholeCameraIntrinsic(
            width=w,
            height=h,
            fx=K[0, 0],
            fy=K[1, 1],
            cx=K[0, 2],
            cy=K[1, 2]
        )

        # Integrate into volume
        # Open3D expects camera-to-world pose (inverse of world-to-camera)
        extrinsic = np.linalg.inv(pose)

        self.volume.integrate(rgbd, intrinsic, extrinsic)

        # Store trajectory
        self.trajectory.append({
            'frame_id': frame_id,
            'pose': pose.tolist(),
            'extrinsic': extrinsic.tolist()
        })

        logger.debug(f"Integrated frame {frame_id}")

    def extract_mesh(self) -> o3d.geometry.TriangleMesh:
        """Extract triangle mesh from TSDF volume"""
        mesh = self.volume.extract_triangle_mesh()
        mesh.compute_vertex_normals()
        return mesh

    def extract_point_cloud(self) -> o3d.geometry.PointCloud:
        """Extract point cloud from TSDF volume"""
        mesh = self.extract_mesh()
        pcd = mesh.sample_points_uniformly(number_of_points=100000)
        return pcd

    def save_results(self, output_dir: str):
        """
        Save reconstruction results.

        Args:
            output_dir: Output directory path
        """
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # Extract and save mesh
        logger.info("Extracting mesh...")
        mesh = self.extract_mesh()
        mesh_path = output_path / 'fused_mesh.ply'
        o3d.io.write_triangle_mesh(str(mesh_path), mesh)
        logger.info(f"Saved mesh: {mesh_path}")

        # Extract and save point cloud
        logger.info("Extracting point cloud...")
        pcd = self.extract_point_cloud()
        pcd_path = output_path / 'fused_pointcloud.ply'
        o3d.io.write_point_cloud(str(pcd_path), pcd)
        logger.info(f"Saved point cloud: {pcd_path} ({len(pcd.points)} points)")

        # Save trajectory
        trajectory_path = output_path / 'trajectory.json'
        with open(trajectory_path, 'w') as f:
            json.dump(self.trajectory, f, indent=2)
        logger.info(f"Saved trajectory: {trajectory_path}")

        return {
            'mesh_path': str(mesh_path),
            'pcd_path': str(pcd_path),
            'trajectory_path': str(trajectory_path),
            'num_points': len(pcd.points)
        }


def run_depth_reconstruction(
    rgb_depth_pairs: List[Tuple[str, str, str]],
    depth_K: np.ndarray,
    output_dir: str = 'output_depth_tsdf',
    voxel_length: float = 0.01,
    depth_unit: str = 'mm',
    use_icp: bool = False
) -> Dict:
    """
    Run depth-only TSDF reconstruction.

    Args:
        rgb_depth_pairs: List of (rgb_path, depth_path, pair_id)
        depth_K: Depth camera intrinsic matrix
        output_dir: Output directory
        voxel_length: Voxel size in meters
        depth_unit: Depth unit ('m' or 'mm')
        use_icp: Whether to use ICP for pose refinement

    Returns:
        Dictionary with reconstruction results
    """
    if not HAS_OPEN3D:
        raise ImportError("Open3D required for depth reconstruction")

    depth_scale = 1000.0 if depth_unit == 'mm' else 1.0

    # Initialize reconstructor
    reconstructor = DepthTSDFReconstructor(
        voxel_length=voxel_length,
        sdf_trunc=voxel_length * 4,
        depth_scale=depth_scale,
        depth_trunc=10.0
    )

    logger.info(f"Starting depth reconstruction with {len(rgb_depth_pairs)} frames")
    logger.info(f"Voxel size: {voxel_length*100:.1f}cm, Depth unit: {depth_unit}")

    # Simple trajectory: assume sequential capture with small motion
    # For better results, use ICP or visual odometry
    poses = []

    for idx, (rgb_path, depth_path, pair_id) in enumerate(rgb_depth_pairs):
        # Load images
        rgb_img = cv2.imread(rgb_path)
        rgb_img = cv2.cvtColor(rgb_img, cv2.COLOR_BGR2RGB)

        depth_img = cv2.imread(depth_path, cv2.IMREAD_UNCHANGED).astype(np.float32)

        # Convert depth to meters
        if depth_unit == 'mm':
            depth_img = depth_img / 1000.0

        # Initialize pose (identity for first frame, then ICP if enabled)
        if idx == 0:
            pose = np.eye(4)
        else:
            if use_icp and idx > 0:
                # Use ICP between consecutive depth frames
                pose = run_depth_icp(
                    prev_depth, depth_img,
                    prev_rgb, rgb_img,
                    depth_K, poses[-1]
                )
            else:
                # Simple incremental pose (assume small motion)
                # This is a placeholder - real implementation needs odometry
                pose = np.eye(4)
                pose[2, 3] = idx * 0.1  # Move 10cm forward each frame

        poses.append(pose)

        # Integrate frame
        reconstructor.integrate_frame(
            rgb_img, depth_img, depth_K, pose, pair_id
        )

        logger.info(f"Integrated frame {idx+1}/{len(rgb_depth_pairs)}: {pair_id}")

        prev_depth = depth_img
        prev_rgb = rgb_img

    # Save results
    logger.info("Saving reconstruction results...")
    results = reconstructor.save_results(output_dir)

    logger.info("=" * 80)
    logger.info("Depth reconstruction completed!")
    logger.info(f"Output directory: {output_dir}")
    logger.info(f"Point cloud: {results['num_points']} points")
    logger.info("=" * 80)

    return results


def run_depth_icp(
    source_depth: np.ndarray,
    target_depth: np.ndarray,
    source_rgb: np.ndarray,
    target_rgb: np.ndarray,
    K: np.ndarray,
    initial_pose: np.ndarray
) -> np.ndarray:
    """
    Run ICP between two depth frames for pose estimation.

    Args:
        source_depth: Source depth image
        target_depth: Target depth image
        source_rgb: Source RGB image
        target_rgb: Target RGB image
        K: Camera intrinsic matrix
        initial_pose: Initial pose guess

    Returns:
        Refined pose (4x4 matrix)
    """
    # Convert depth to point clouds
    def depth_to_pcd(depth, rgb, K):
        h, w = depth.shape
        fx, fy = K[0, 0], K[1, 1]
        cx, cy = K[0, 2], K[1, 2]

        u, v = np.meshgrid(np.arange(w), np.arange(h))
        u = u.flatten()
        v = v.flatten()
        z = depth.flatten()

        valid = z > 0
        u, v, z = u[valid], v[valid], z[valid]

        x = (u - cx) * z / fx
        y = (v - cy) * z / fy

        points = np.stack([x, y, z], axis=-1)
        colors = rgb.reshape(-1, 3)[valid] / 255.0

        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(points)
        pcd.colors = o3d.utility.Vector3dVector(colors)

        return pcd

    source_pcd = depth_to_pcd(source_depth, source_rgb, K)
    target_pcd = depth_to_pcd(target_depth, target_rgb, K)

    # Downsample for speed
    source_pcd = source_pcd.voxel_down_sample(voxel_size=0.02)
    target_pcd = target_pcd.voxel_down_sample(voxel_size=0.02)

    # Estimate normals
    source_pcd.estimate_normals()
    target_pcd.estimate_normals()

    # Run ICP
    threshold = 0.05  # 5cm
    reg_result = o3d.pipelines.registration.registration_icp(
        source_pcd, target_pcd, threshold, initial_pose,
        o3d.pipelines.registration.TransformationEstimationPointToPlane()
    )

    return reg_result.transformation


if __name__ == '__main__':
    # Test
    import argparse
    import sys
    from .utils import find_rgb_depth_pairs, setup_logging
    from .calib_io import load_camera_info

    parser = argparse.ArgumentParser(description='Depth-only TSDF reconstruction')
    parser.add_argument('--rgb-dir', required=True, help='RGB images directory')
    parser.add_argument('--depth-dir', required=True, help='Depth images directory')
    parser.add_argument('--calib', required=True, help='Depth camera calibration JSON')
    parser.add_argument('--output-dir', default='output_depth_tsdf', help='Output directory')
    parser.add_argument('--voxel-size', type=float, default=0.01, help='Voxel size in meters')
    parser.add_argument('--depth-unit', choices=['m', 'mm'], default='mm', help='Depth unit')
    parser.add_argument('--use-icp', action='store_true', help='Use ICP for pose estimation')

    args = parser.parse_args()

    setup_logging('INFO')

    try:
        # Load calibration
        calib = load_camera_info(args.calib)

        # Find pairs
        pairs = find_rgb_depth_pairs(args.rgb_dir, args.depth_dir)

        if not pairs:
            logger.error("No RGB-Depth pairs found!")
            sys.exit(1)

        # Run reconstruction
        results = run_depth_reconstruction(
            pairs,
            calib.K,
            output_dir=args.output_dir,
            voxel_length=args.voxel_size,
            depth_unit=args.depth_unit,
            use_icp=args.use_icp
        )

        print(f"\n✅ Reconstruction complete!")
        print(f"   Point cloud: {results['pcd_path']}")
        print(f"   Points: {results['num_points']}")

    except Exception as e:
        logger.error(f"Reconstruction failed: {e}", exc_info=True)
        sys.exit(1)
