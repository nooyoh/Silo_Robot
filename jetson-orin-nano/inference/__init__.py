"""Runtime pipeline for the SiloRobot Orin vision server (crack/corrosion segmentation).

원본: jetson-orin-nano/inference/ (단일클래스 crack detection 전용).
이 사본은 cc_seg_v1(YOLOv8s-seg, 2클래스 crack/corrosion) 모델에 맞춰
마스크 폴리곤 추출을 추가한 버전이다. docs/orin_tensorrt_deploy.md 참고.
"""
