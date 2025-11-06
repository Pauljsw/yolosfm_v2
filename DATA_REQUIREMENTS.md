# 전체 파이프라인 Input 데이터 요구사항

## 📂 필수 디렉토리 구조

파이프라인 실행 전 다음 구조로 데이터를 준비해야 합니다:

```
yolosfm_v2/
├── data/
│   ├── rgb/                          # ✅ 필수: RGB 이미지
│   │   ├── camera_RGB_0_0.png
│   │   ├── camera_RGB_0_1.png
│   │   ├── camera_RGB_0_2.png
│   │   └── ... (최소 5장 이상 권장)
│   │
│   └── depth/                        # ✅ 필수: Depth 이미지
│       ├── camera_DPT_0_0.png       # RGB와 파일명 매칭!
│       ├── camera_DPT_0_1.png
│       ├── camera_DPT_0_2.png
│       └── ...
│
├── calib/                            # ✅ 필수: 카메라 캘리브레이션
│   ├── rgb_camera_info.json
│   └── depth_camera_info.json
│
├── models/                           # ✅ 필수: YOLO 모델
│   └── best.pt
│
├── configs/                          # ✅ 필수: 설정 파일
│   ├── default.yaml                 # 메인 설정
│   └── yolo_data.yaml               # YOLO 클래스 정의
│
└── (이하는 파이프라인이 자동 생성)
    ├── data/
    │   ├── sfm/                      # Phase 0 출력 (COLMAP)
    │   └── yolo_masks/               # Phase 4 출력 (YOLO)
    │
    ├── output_depth_tsdf/            # Phase 1 출력
    └── outputs/                      # Phase 5-7 출력
```

---

## ✅ 필수 Input 데이터 상세

### 1. RGB 이미지 (`data/rgb/`)

**형식**: PNG 파일
**해상도**: 3840×2160 (Orbbec Femto Bolt 기준)
**파일명 규칙**: `camera_RGB_X_Y.png`
  - X: 첫 번째 인덱스 (예: 0, 1, 2)
  - Y: 두 번째 인덱스 (예: 0, 1, 2)
  - 예: `camera_RGB_0_0.png`, `camera_RGB_0_1.png`

**필요 이유**:
- Phase 0 (SFM): 카메라 포즈 추정
- Phase 3: Depth 정렬 대상
- Phase 4: YOLO 추론 입력

**최소 수량**: 5장 이상 (SFM 품질 보장)
**권장 수량**: 30-100장 (충분한 중복도)

**예시**:
```
data/rgb/camera_RGB_0_0.png
data/rgb/camera_RGB_0_1.png
data/rgb/camera_RGB_0_2.png
data/rgb/camera_RGB_1_0.png
data/rgb/camera_RGB_1_1.png
```

---

### 2. Depth 이미지 (`data/depth/`)

**형식**: PNG 파일 (16-bit 또는 float)
**해상도**: 512×512 (Orbbec Femto Bolt 기준)
**파일명 규칙**: `camera_DPT_X_Y.png`
  - **RGB와 동일한 X, Y 인덱스 사용!**
  - 예: `camera_DPT_0_0.png` ↔ `camera_RGB_0_0.png` (매칭)

**단위**: mm 또는 m (자동 탐지됨)
  - mm: 값 1000 = 1미터
  - m: 값 1.0 = 1미터

**필요 이유**:
- Phase 1: Depth 기준 모델 생성
- Phase 3: RGB로 정렬
- Phase 5: 3D 투영에 사용

**중요**:
- RGB와 **정확히 같은 시점**에서 촬영된 이미지
- 파일명의 X_Y가 RGB와 **반드시 일치**해야 함

**예시**:
```
data/depth/camera_DPT_0_0.png  (↔ camera_RGB_0_0.png)
data/depth/camera_DPT_0_1.png  (↔ camera_RGB_0_1.png)
data/depth/camera_DPT_0_2.png  (↔ camera_RGB_0_2.png)
```

---

### 3. RGB 카메라 캘리브레이션 (`calib/rgb_camera_info.json`)

**형식**: JSON

**필수 파라미터**:
```json
{
  "width": 3840,
  "height": 2160,
  "K": [
    [2246.03125, 0.0, 1903.4835205078125],
    [0.0, 2244.83740234375, 1091.5631103515625],
    [0.0, 0.0, 1.0]
  ],
  "D": [
    0.0779024288058281,
    -0.10618548840284348,
    -0.0002932515926659107,
    -4.253092629369348e-05,
    0.04364937171339989,
    0.0, 0.0, 0.0
  ],
  "distortion_model": "rational_polynomial"
}
```

**파라미터 설명**:
- `width`, `height`: 이미지 해상도
- `K`: 내부 파라미터 행렬
  - `K[0][0]`: fx (초점거리 x)
  - `K[1][1]`: fy (초점거리 y)
  - `K[0][2]`: cx (주점 x)
  - `K[1][2]`: cy (주점 y)
- `D`: 왜곡 계수
- `distortion_model`: "rational_polynomial" 또는 "radial_tangential"

**필요 이유**:
- Phase 0 (SFM): COLMAP 초기값
- Phase 3: Depth 정렬
- Phase 5: 3D 백프로젝션

**획득 방법**:
1. ROS camera calibration: `camera_info` 토픽
2. Orbbec SDK: API로 조회
3. OpenCV 캘리브레이션: 체커보드 패턴 사용

---

### 4. Depth 카메라 캘리브레이션 (`calib/depth_camera_info.json`)

**형식**: JSON

**필수 파라미터**:
```json
{
  "width": 512,
  "height": 512,
  "K": [
    [252.00250244140625, 0.0, 263.51019287109375],
    [0.0, 251.96585083007812, 260.2386169433594],
    [0.0, 0.0, 1.0]
  ],
  "D": [
    22.01300811767578,
    12.45872974395752,
    8.35928221931681e-05,
    5.2367677199072205e-06,
    0.5336462259292603,
    22.301536560058594,
    19.940372467041016,
    3.084506034851074
  ],
  "distortion_model": "rational_polynomial"
}
```

**필요 이유**:
- Phase 1: Depth 3D 백프로젝션
- Phase 3: Depth 정렬

**Orbbec Femto Bolt의 경우**:
- RGB와 Depth가 동일 장치이므로 Extrinsics 불필요 (Identity 가정 가능)
- 하드웨어 정렬 모드 사용 가능 (`use_simple_resize: true`)

---

### 5. YOLO Segmentation 모델 (`models/best.pt`)

**형식**: PyTorch 모델 (.pt 파일)
**학습 프레임워크**: Ultralytics YOLOv8 또는 YOLO11

**필요 이유**:
- Phase 4: RGB 이미지에서 결함 탐지

**학습 데이터**:
- **입력**: RGB 이미지 (3840×2160 또는 리사이즈된 크기)
- **출력**: Segmentation masks (polygon 형식)
- **클래스**: crack, spalling, efflorescence 등

**모델 준비 방법**:
1. Labelme/CVAT으로 annotate
2. YOLO 형식으로 변환
3. Ultralytics로 학습:
   ```bash
   yolo segment train data=configs/yolo_data.yaml model=yolo11x-seg.pt
   ```

**모델 위치**:
```
models/best.pt
```

**파일 크기**: 수십~수백 MB

---

### 6. YOLO 데이터 설정 (`configs/yolo_data.yaml`)

**형식**: YAML

**필수 내용**:
```yaml
# YOLO dataset configuration
path: ./data  # Dataset root directory
train: train/images
val: val/images

# Class names (순서 중요!)
names:
  0: crack
  1: efflorescence
  2: detachment
  3: leak
  4: spalling
  5: material separation
  6: rebar
  7: damage
  8: exhilaration
```

**필요 이유**:
- Phase 4: YOLO 모델이 클래스명을 참조
- Pipeline: 클래스 ID → 이름 매핑

**주의사항**:
- `names`의 순서는 모델 학습 시 사용한 순서와 **정확히 일치**해야 함
- `configs/default.yaml`의 `classes` 섹션과 일치 확인

---

### 7. 메인 파이프라인 설정 (`configs/default.yaml`)

**형식**: YAML

**필수 섹션**:

#### a) 경로 설정
```yaml
paths:
  rgb_dir: data/rgb
  depth_dir: data/depth
  masks_dir: data/yolo_masks
  sfm_dir: data/sfm
  depth_gt_dir: output_depth_tsdf
  calib_rgb: calib/rgb_camera_info.json
  calib_depth: calib/depth_camera_info.json
  out_dir: outputs
```

#### b) YOLO 설정
```yaml
yolo:
  weights: models/best.pt
  data_config: configs/yolo_data.yaml
  conf: 0.20                # 신뢰도 임계값
  iou: 0.45                 # NMS IoU
  img_size: 1280            # 추론 이미지 크기
  device: null              # GPU 번호 or null (auto)
  max_det: 300
```

#### c) Phase 1-2 설정
```yaml
# Phase 1: Depth 기준 모델
depth_reconstruction:
  voxel_size_m: 0.01
  depth_unit: "auto"
  use_icp: false

# Phase 2: 스케일 정합
scale_alignment:
  use_feature_matching: true
  max_points: 10000
```

#### d) Phase 3 설정
```yaml
align:
  in_depth_unit: "auto"
  use_simple_resize: false    # Orbbec: true
  hole_fill: true
  joint_bilateral: true
```

#### e) Phase 5-7 설정
```yaml
fusion:
  voxel_size_cm: 0.5
  prob_thresh: 0.55

merge:
  dbscan_eps_voxel_mul: 3.0
  dbscan_min_pts: 10
  iou_merge_thresh: 0.3

measure:
  crack_min_length_cm: 5.0
  area_min_m2: 0.001

classes:
  crack: 0
  efflorescence: 1
  # ... (yolo_data.yaml과 일치)
```

---

## 📊 Input 데이터 체크리스트

파이프라인 실행 전 확인:

### 필수 데이터 (7개)
- [ ] RGB 이미지 (data/rgb/*.png) - 5장 이상
- [ ] Depth 이미지 (data/depth/*.png) - RGB와 개수 동일
- [ ] RGB 캘리브레이션 (calib/rgb_camera_info.json)
- [ ] Depth 캘리브레이션 (calib/depth_camera_info.json)
- [ ] YOLO 모델 (models/best.pt)
- [ ] YOLO 데이터 설정 (configs/yolo_data.yaml)
- [ ] 파이프라인 설정 (configs/default.yaml)

### 파일명 규칙 확인
- [ ] RGB: `camera_RGB_X_Y.png`
- [ ] Depth: `camera_DPT_X_Y.png` (RGB와 X_Y 일치)

### 캘리브레이션 확인
- [ ] RGB K 행렬이 3×3
- [ ] Depth K 행렬이 3×3
- [ ] 왜곡 계수 D가 존재
- [ ] width/height가 실제 이미지와 일치

### YOLO 확인
- [ ] best.pt 파일이 존재
- [ ] yolo_data.yaml의 클래스 순서가 학습 시와 동일
- [ ] default.yaml의 classes 섹션과 일치

---

## 🔍 데이터 검증 명령어

```bash
# 1. RGB-Depth 파일 개수 확인
ls data/rgb/*.png | wc -l
ls data/depth/*.png | wc -l
# → 두 개수가 같아야 함

# 2. 파일명 매칭 확인
python -c "
from pathlib import Path
import re

rgb_files = sorted(Path('data/rgb').glob('camera_RGB_*.png'))
depth_files = sorted(Path('data/depth').glob('camera_DPT_*.png'))

rgb_ids = [re.search(r'RGB_(\d+_\d+)', f.name).group(1) for f in rgb_files]
depth_ids = [re.search(r'DPT_(\d+_\d+)', f.name).group(1) for f in depth_files]

missing = set(rgb_ids) - set(depth_ids)
if missing:
    print(f'Missing depth for: {missing}')
else:
    print(f'✓ All {len(rgb_ids)} RGB-Depth pairs matched!')
"

# 3. 캘리브레이션 파일 확인
python -c "
import json
with open('calib/rgb_camera_info.json') as f:
    rgb = json.load(f)
    print(f'RGB: {rgb[\"width\"]}x{rgb[\"height\"]}')
    print(f'RGB fx: {rgb[\"K\"][0][0]:.1f}')

with open('calib/depth_camera_info.json') as f:
    depth = json.load(f)
    print(f'Depth: {depth[\"width\"]}x{depth[\"height\"]}')
    print(f'Depth fx: {depth[\"K\"][0][0]:.1f}')
"

# 4. YOLO 모델 확인
python -c "
from pathlib import Path
model = Path('models/best.pt')
if model.exists():
    print(f'✓ YOLO model: {model} ({model.stat().st_size / 1024 / 1024:.1f} MB)')
else:
    print('✗ YOLO model not found!')
"

# 5. 전체 데이터 검증 (파이프라인 내장)
python -m src.pipeline full --config configs/default.yaml --log-level DEBUG
# → 에러 발생 시 로그에서 누락된 데이터 확인
```

---

## 🚨 자주 발생하는 문제

### 1. "No RGB-Depth pairs found"
**원인**: 파일명 규칙 불일치
**해결**:
- RGB: `camera_RGB_0_0.png` 형식
- Depth: `camera_DPT_0_0.png` 형식 (X_Y 일치)

### 2. "YOLO model not found"
**원인**: `models/best.pt` 경로 오류
**해결**:
```bash
mkdir -p models
# YOLO 모델을 models/best.pt로 복사
```

### 3. "Camera calibration mismatch"
**원인**: JSON 파일의 width/height가 실제 이미지와 다름
**해결**:
```python
# RGB 이미지 크기 확인
import cv2
img = cv2.imread('data/rgb/camera_RGB_0_0.png')
print(img.shape)  # (H, W, 3)
# → calib/rgb_camera_info.json의 width, height와 일치해야 함
```

### 4. "Depth unit mismatch"
**원인**: Depth 단위가 예상과 다름
**해결**:
```yaml
# configs/default.yaml
align:
  in_depth_unit: "mm"  # 명시적으로 지정 (auto 대신)
```

### 5. "COLMAP reconstruction failed"
**원인**: RGB 이미지가 너무 적거나 중복도 부족
**해결**:
- 최소 5장 이상 촬영
- 인접 프레임 간 60-80% 오버랩 유지

---

## 📋 데이터 준비 순서 (권장)

1. **RGB-D 이미지 촬영**
   - Orbbec Femto Bolt로 촬영
   - ROS bag 또는 직접 PNG 저장
   - 파일명 규칙 준수

2. **카메라 캘리브레이션**
   - ROS camera_calibration 사용
   - 또는 Orbbec SDK에서 파라미터 추출
   - JSON 파일로 저장

3. **YOLO 모델 학습**
   - Annotate (Labelme/CVAT)
   - YOLO 형식 변환
   - Ultralytics로 학습
   - best.pt 저장

4. **설정 파일 작성**
   - yolo_data.yaml (클래스 정의)
   - default.yaml (경로 및 파라미터)

5. **데이터 검증**
   - 위 체크리스트 확인
   - 검증 명령어 실행

6. **파이프라인 실행**
   ```bash
   python -m src.pipeline full --config configs/default.yaml
   ```

---

## 📧 추가 지원

데이터 준비 중 문제가 발생하면:
1. `--log-level DEBUG`로 상세 로그 확인
2. 위 검증 명령어로 데이터 확인
3. `IMPLEMENTATION_GUIDE.md`의 Troubleshooting 참고

---

**전체 input 데이터가 준비되면 파이프라인이 자동으로 나머지를 생성합니다!** 🚀
