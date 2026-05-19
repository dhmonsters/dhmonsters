# 이 PC 고유의 하드웨어 ID(HWID)를 생성하는 모듈
import hashlib
import subprocess


def get_hwid() -> str:
    """CPU ID + 메인보드 Serial + C드라이브 Volume Serial + BIOS Serial
    을 조합해 16자리 고유 ID를 반환.

    같은 PC에서는 항상 동일한 값이 나오고,
    다른 PC로 파일을 복사하면 값이 달라진다.
    MAC 주소·컴퓨터 이름처럼 변경 가능한 정보는 사용하지 않는다.
    """
    parts = [
        _wmic("cpu",       "ProcessorId"),      # CPU 하드웨어 ID
        _wmic("baseboard", "SerialNumber"),      # 메인보드 시리얼
        _get_volume_serial(),                    # C드라이브 볼륨 시리얼
        _wmic("bios",      "SerialNumber"),      # BIOS 시리얼
    ]
    raw = "|".join(parts)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest[:16].upper()


def _wmic(alias: str, field: str) -> str:
    """wmic 명령으로 하드웨어 정보를 가져온다. 실패하면 빈 문자열 반환."""
    try:
        out = subprocess.check_output(
            ["wmic", alias, "get", field],
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000,   # CREATE_NO_WINDOW — 콘솔 창 숨김
            timeout=5,
        ).decode("utf-8", errors="ignore")
        # 출력 형식: "Field\r\nValue\r\n\r\n" → 값만 추출
        lines = [l.strip() for l in out.splitlines() if l.strip()]
        return lines[1] if len(lines) >= 2 else ""
    except Exception:
        return ""


def _get_volume_serial() -> str:
    """C 드라이브 볼륨 시리얼 번호. 실패하면 빈 문자열 반환."""
    try:
        import win32api
        info = win32api.GetVolumeInformation("C:\\")
        return str(info[1])
    except Exception:
        return ""
