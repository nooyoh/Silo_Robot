# 데이터셋 출처·라이선스 (crack_corrosion_seg v1)

> 보고서 부록용. 최종 채택한 소스만 남기고, 실제 다운로드 후 이미지·인스턴스 수를 채운다.

## 채택 데이터셋

| 소스 | 클래스 | 라이선스 | URL | 채택 이미지 | 인스턴스(train/val/test) |
|---|---|---|---|---|---|
| Steelcrack (He et al., 2024) | crack | Apache-2.0 | https://github.com/hzlbbfrog/Civil-dataset | 4,355 (전량) | 8,653 / 1,358 / 1,142 |
| corrosion-instance-segmentation-sfcpc (cawilai) v16 | corrosion | CC BY 4.0 (data.yaml 명시) | https://universe.roboflow.com/cawilai-interns-july-2023/corrosion-instance-segmentation-sfcpc | 4,942 (전량) | 아래 corrosion 합계에 포함 |
| corrosion-i0q5q (corrosion-aom4m) v11 | corrosion | CC BY 4.0 (data.yaml 명시) | https://universe.roboflow.com/corrosion-aom4m/corrosion-i0q5q | 1,500 (원본 ~32k 중 캡) | — |

병합 결과 (`Dataset/crack_corrosion_seg`, 2026-09-04):
- 총 10,267 이미지 — train 8,506 / val 1,000 / test 761
- 인스턴스: crack 11,153 · corrosion 71,722 (부식은 폴리곤이 여러 조각으로 나뉘어 인스턴스 수가 많음)

> 두 Roboflow 데이터셋 모두 data.yaml `roboflow.license: CC BY 4.0` 명시 확인함.
> rust-detection-38s6e 는 바운딩박스 전용(세그 아님) + 잡클래스라 **제외**.
> 부식 데이터에 Roboflow 자동증강본(HDR·과채도·픽셀화)이 섞여 있음 — Phase B 에서 원본만 재수집 검토.

## 인용

### Steelcrack / BGCrack
```bibtex
@article{he2024crack,
  title   = {Crack segmentation on steel structures using boundary guidance model},
  author  = {He, ... and others},
  journal = {Automation in Construction},
  year    = {2024}
}
```

### Roboflow Universe
```
<프로젝트명>, Roboflow Universe, <워크스페이스>, <연도>.
https://universe.roboflow.com/<workspace>/<project>  (accessed 2026-09).
```

## 전처리 요약 (재현용)

- Steelcrack: 시맨틱 이진 마스크 PNG → `cv2.findContours` + `approxPolyDP` (eps=0.004·arc, 점≤100,
  면적<3e-5 제거) → YOLO 폴리곤. `scripts/steelcrack_to_yolo_seg.py`.
- Roboflow: `download("yolov8")` 로 이미 폴리곤 포맷. 클래스 id 만 corrosion(1)로 remap.
- 병합: `scripts/merge_and_split.py`, 해시 기반 train/val/test = 80/10/10, seed=42.
- 최종: `Dataset/crack_corrosion_seg/`, `names: {0: crack, 1: corrosion}`.
