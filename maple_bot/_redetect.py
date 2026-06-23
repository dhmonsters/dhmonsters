# 기존 16판 mp4에 shape_yolo 재실행 — 버렸던 박스 w/h 복원. <name>.wjsonl 저장.
# 패널은 원본 jsonl로 추적하고, 이 w/h는 박스면적 스파이크(병합 단서)로만 조회.
import sys, os, json, glob, cv2
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.stdout.reconfigure(encoding='utf-8')
from core.shape_yolo import ShapeYolo
ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    sy = ShapeYolo()
    if not sy.enabled:
        print("detector 비활성"); return
    names = sorted(os.path.basename(d) for d in
                   glob.glob(os.path.join(ROOT, '_gt_frames', '*')) if os.path.isdir(d))
    for name in names:
        mp4 = os.path.join(ROOT, '_record_debug', name + '.mp4')
        if not os.path.exists(mp4):
            continue
        cap = cv2.VideoCapture(mp4); out = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            boxes = sy._infer(f, 0.1)
            row = [[round(float((b[0]+b[2])/2), 1), round(float((b[1]+b[3])/2), 1),
                    round(float(b[2]-b[0]), 1), round(float(b[3]-b[1]), 1),
                    round(float(b[4]), 3)] for b in boxes]
            out.append(row)
        cap.release()
        with open(mp4[:-4] + '.wjsonl', 'w', encoding='utf-8') as fp:
            for row in out:
                fp.write(json.dumps(row) + '\n')
        print(f"{name}: {len(out)}프레임 재검출 저장")


if __name__ == "__main__":
    main()
