# CUDA 드라이버를 직접 호출해 구형 GPU의 메모리와 연산 성능을 검사한다.
from __future__ import annotations

import ctypes
import os
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Iterator


CUDA_SUCCESS = 0
NVRTC_SUCCESS = 0
ROI_WIDTH = 488
ROI_HEIGHT = 328
BENCHMARK_BATCH = 32
BENCHMARK_ITERATIONS = 120


@dataclass(frozen=True)
class ProbeMetrics:
    gpu_name: str
    compute_major: int
    compute_minor: int
    dedicated_total_mb: float
    dedicated_free_mb: float
    allocation_512mb: bool
    kernel_ok: bool
    equivalent_fps: float
    driver_version: int = 0
    benchmark_ms: float = 0.0


@dataclass(frozen=True)
class ProbeDecision:
    status: str
    reasons: tuple[str, ...]


def compile_arch_option(major: int, minor: int) -> str:
    return f"--gpu-architecture=compute_{int(major)}{int(minor)}"


def evaluate_probe(metrics: ProbeMetrics) -> ProbeDecision:
    if not metrics.kernel_ok:
        return ProbeDecision("FAIL", ("CUDA_KERNEL_FAILED",))

    reasons: list[str] = []
    if metrics.dedicated_total_mb < 3584.0:
        reasons.append("DEDICATED_VRAM_BELOW_3_5_GB")
    if metrics.dedicated_free_mb < 1024.0:
        reasons.append("FREE_VRAM_BELOW_1024_MB")
    if not metrics.allocation_512mb:
        reasons.append("VRAM_512_MB_ALLOCATION_FAILED")
    if metrics.equivalent_fps < 60.0:
        reasons.append("BENCHMARK_BELOW_60_FPS")
    return ProbeDecision("SLOW" if reasons else "PASS", tuple(reasons))


def resolve_nvrtc_root() -> Path:
    if bool(getattr(sys, "frozen", False)):
        return Path(sys.executable).resolve().parent
    return Path(
        r"C:\Users\PC\AppData\Local\Programs\Python\Python314\Lib\site-packages\torch\lib"
    )


@contextmanager
def temporary_working_directory(path: str | Path) -> Iterator[None]:
    original = Path.cwd()
    os.chdir(Path(path))
    try:
        yield
    finally:
        os.chdir(original)


def run_cuda_probe(nvrtc_root: str | Path | None = None) -> ProbeMetrics:
    root = Path(nvrtc_root) if nvrtc_root else resolve_nvrtc_root()
    driver = _CudaDriver()
    driver.initialize()
    nvrtc = _Nvrtc(root / "nvrtc64_120_0.dll")

    device = driver.first_device()
    gpu_name = driver.device_name(device)
    major = driver.device_attribute(device, 75)
    minor = driver.device_attribute(device, 76)
    driver_version = driver.driver_version()
    context = driver.create_context(device)

    benchmark_ms = 0.0
    equivalent_fps = 0.0
    allocation_ok = False
    kernel_ok = False
    total_bytes = 0
    free_bytes = 0
    try:
        free_bytes, total_bytes = driver.memory_info()
        allocation_ok = driver.try_allocation(512 * 1024 * 1024)
        ptx = nvrtc.compile(_KERNEL_SOURCE, compile_arch_option(major, minor))
        benchmark_ms, equivalent_fps = driver.run_benchmark(ptx)
        kernel_ok = True
        free_bytes, total_bytes = driver.memory_info()
    finally:
        driver.destroy_context(context)

    return ProbeMetrics(
        gpu_name=gpu_name,
        compute_major=major,
        compute_minor=minor,
        dedicated_total_mb=round(total_bytes / 1024 / 1024, 1),
        dedicated_free_mb=round(free_bytes / 1024 / 1024, 1),
        allocation_512mb=allocation_ok,
        kernel_ok=kernel_ok,
        equivalent_fps=round(equivalent_fps, 1),
        driver_version=driver_version,
        benchmark_ms=round(benchmark_ms, 3),
    )


class _CudaDriver:
    def __init__(self) -> None:
        self.dll = ctypes.WinDLL("nvcuda.dll")
        self.cu_init = self._function("cuInit", [ctypes.c_uint])
        self.cu_driver_get_version = self._function(
            "cuDriverGetVersion", [ctypes.POINTER(ctypes.c_int)]
        )
        self.cu_device_get_count = self._function(
            "cuDeviceGetCount", [ctypes.POINTER(ctypes.c_int)]
        )
        self.cu_device_get = self._function(
            "cuDeviceGet", [ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        )
        self.cu_device_get_name = self._function(
            "cuDeviceGetName", [ctypes.c_char_p, ctypes.c_int, ctypes.c_int]
        )
        self.cu_device_get_attribute = self._function(
            "cuDeviceGetAttribute",
            [ctypes.POINTER(ctypes.c_int), ctypes.c_int, ctypes.c_int],
        )
        self.cu_ctx_create = self._function_any(
            ("cuCtxCreate_v2", "cuCtxCreate"),
            [ctypes.POINTER(ctypes.c_void_p), ctypes.c_uint, ctypes.c_int],
        )
        self.cu_ctx_destroy = self._function_any(
            ("cuCtxDestroy_v2", "cuCtxDestroy"), [ctypes.c_void_p]
        )
        self.cu_ctx_synchronize = self._function("cuCtxSynchronize", [])
        self.cu_mem_get_info = self._function_any(
            ("cuMemGetInfo_v2", "cuMemGetInfo"),
            [ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)],
        )
        self.cu_mem_alloc = self._function_any(
            ("cuMemAlloc_v2", "cuMemAlloc"),
            [ctypes.POINTER(ctypes.c_uint64), ctypes.c_size_t],
        )
        self.cu_mem_free = self._function_any(
            ("cuMemFree_v2", "cuMemFree"), [ctypes.c_uint64]
        )
        self.cu_memset_d32 = self._function_any(
            ("cuMemsetD32_v2", "cuMemsetD32"),
            [ctypes.c_uint64, ctypes.c_uint, ctypes.c_size_t],
        )
        self.cu_module_load_data = self._function(
            "cuModuleLoadData", [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p]
        )
        self.cu_module_unload = self._function("cuModuleUnload", [ctypes.c_void_p])
        self.cu_module_get_function = self._function(
            "cuModuleGetFunction",
            [ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_char_p],
        )
        self.cu_launch_kernel = self._function(
            "cuLaunchKernel",
            [
                ctypes.c_void_p,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_uint,
                ctypes.c_void_p,
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.POINTER(ctypes.c_void_p),
            ],
        )

    def _function(self, name: str, argtypes: list[object]):
        function = getattr(self.dll, name)
        function.argtypes = argtypes
        function.restype = ctypes.c_int
        return function

    def _function_any(self, names: tuple[str, ...], argtypes: list[object]):
        for name in names:
            try:
                return self._function(name, argtypes)
            except AttributeError:
                continue
        raise RuntimeError("CUDA driver function missing: " + ", ".join(names))

    @staticmethod
    def _check(result: int, operation: str) -> None:
        if result != CUDA_SUCCESS:
            raise RuntimeError(f"{operation} failed with CUDA error {result}")

    def initialize(self) -> None:
        self._check(self.cu_init(0), "cuInit")

    def driver_version(self) -> int:
        value = ctypes.c_int()
        self._check(self.cu_driver_get_version(ctypes.byref(value)), "cuDriverGetVersion")
        return int(value.value)

    def first_device(self) -> int:
        count = ctypes.c_int()
        self._check(self.cu_device_get_count(ctypes.byref(count)), "cuDeviceGetCount")
        if count.value < 1:
            raise RuntimeError("CUDA_DEVICE_NOT_FOUND")
        device = ctypes.c_int()
        self._check(self.cu_device_get(ctypes.byref(device), 0), "cuDeviceGet")
        return int(device.value)

    def device_name(self, device: int) -> str:
        buffer = ctypes.create_string_buffer(256)
        self._check(self.cu_device_get_name(buffer, len(buffer), device), "cuDeviceGetName")
        return buffer.value.decode("utf-8", errors="replace")

    def device_attribute(self, device: int, attribute: int) -> int:
        value = ctypes.c_int()
        self._check(
            self.cu_device_get_attribute(ctypes.byref(value), attribute, device),
            "cuDeviceGetAttribute",
        )
        return int(value.value)

    def create_context(self, device: int) -> ctypes.c_void_p:
        context = ctypes.c_void_p()
        self._check(self.cu_ctx_create(ctypes.byref(context), 0, device), "cuCtxCreate")
        return context

    def destroy_context(self, context: ctypes.c_void_p) -> None:
        if context:
            self.cu_ctx_destroy(context)

    def memory_info(self) -> tuple[int, int]:
        free_bytes = ctypes.c_size_t()
        total_bytes = ctypes.c_size_t()
        self._check(
            self.cu_mem_get_info(ctypes.byref(free_bytes), ctypes.byref(total_bytes)),
            "cuMemGetInfo",
        )
        return int(free_bytes.value), int(total_bytes.value)

    def try_allocation(self, size: int) -> bool:
        pointer = ctypes.c_uint64()
        result = self.cu_mem_alloc(ctypes.byref(pointer), size)
        if result != CUDA_SUCCESS:
            return False
        self.cu_mem_free(pointer)
        return True

    def run_benchmark(self, ptx: bytes) -> tuple[float, float]:
        ptx_buffer = ctypes.create_string_buffer(ptx)
        module = ctypes.c_void_p()
        self._check(
            self.cu_module_load_data(ctypes.byref(module), ctypes.cast(ptx_buffer, ctypes.c_void_p)),
            "cuModuleLoadData",
        )
        function = ctypes.c_void_p()
        src = ctypes.c_uint64()
        dst = ctypes.c_uint64()
        frame_count = ROI_WIDTH * ROI_HEIGHT * BENCHMARK_BATCH
        bytes_per_buffer = frame_count * ctypes.sizeof(ctypes.c_float)
        try:
            self._check(
                self.cu_module_get_function(
                    ctypes.byref(function), module, b"roi_conv3x3"
                ),
                "cuModuleGetFunction",
            )
            self._check(self.cu_mem_alloc(ctypes.byref(src), bytes_per_buffer), "cuMemAlloc src")
            self._check(self.cu_mem_alloc(ctypes.byref(dst), bytes_per_buffer), "cuMemAlloc dst")
            self._check(
                self.cu_memset_d32(src, 0x3F800000, frame_count), "cuMemsetD32"
            )
            width = ctypes.c_int(ROI_WIDTH)
            height = ctypes.c_int(ROI_HEIGHT * BENCHMARK_BATCH)
            arguments = (ctypes.c_void_p * 4)(
                ctypes.cast(ctypes.byref(src), ctypes.c_void_p),
                ctypes.cast(ctypes.byref(dst), ctypes.c_void_p),
                ctypes.cast(ctypes.byref(width), ctypes.c_void_p),
                ctypes.cast(ctypes.byref(height), ctypes.c_void_p),
            )

            def launch() -> None:
                self._check(
                    self.cu_launch_kernel(
                        function,
                        (ROI_WIDTH + 15) // 16,
                        (height.value + 15) // 16,
                        1,
                        16,
                        16,
                        1,
                        0,
                        None,
                        arguments,
                        None,
                    ),
                    "cuLaunchKernel",
                )

            for _ in range(10):
                launch()
            self._check(self.cu_ctx_synchronize(), "warmup synchronize")
            started = time.perf_counter()
            for _ in range(BENCHMARK_ITERATIONS):
                launch()
            self._check(self.cu_ctx_synchronize(), "benchmark synchronize")
            elapsed = time.perf_counter() - started
            average_ms = elapsed * 1000.0 / BENCHMARK_ITERATIONS
            equivalent_fps = BENCHMARK_BATCH * BENCHMARK_ITERATIONS / elapsed
            return average_ms, equivalent_fps
        finally:
            if dst.value:
                self.cu_mem_free(dst)
            if src.value:
                self.cu_mem_free(src)
            if module:
                self.cu_module_unload(module)


class _Nvrtc:
    def __init__(self, path: Path) -> None:
        if not path.is_file():
            raise FileNotFoundError(f"NVRTC DLL not found: {path}")
        self.root = path.parent
        self._dll_directory = os.add_dll_directory(str(path.parent))
        self.dll = ctypes.WinDLL(str(path))
        self.create_program = self._function(
            "nvrtcCreateProgram",
            [
                ctypes.POINTER(ctypes.c_void_p),
                ctypes.c_char_p,
                ctypes.c_char_p,
                ctypes.c_int,
                ctypes.c_void_p,
                ctypes.c_void_p,
            ],
        )
        self.compile_program = self._function(
            "nvrtcCompileProgram",
            [ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_char_p)],
        )
        self.get_ptx_size = self._function(
            "nvrtcGetPTXSize", [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        )
        self.get_ptx = self._function(
            "nvrtcGetPTX", [ctypes.c_void_p, ctypes.c_char_p]
        )
        self.get_log_size = self._function(
            "nvrtcGetProgramLogSize", [ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t)]
        )
        self.get_log = self._function(
            "nvrtcGetProgramLog", [ctypes.c_void_p, ctypes.c_char_p]
        )
        self.destroy_program = self._function(
            "nvrtcDestroyProgram", [ctypes.POINTER(ctypes.c_void_p)]
        )

    def _function(self, name: str, argtypes: list[object]):
        function = getattr(self.dll, name)
        function.argtypes = argtypes
        function.restype = ctypes.c_int
        return function

    def compile(self, source: str, architecture: str) -> bytes:
        program = ctypes.c_void_p()
        result = self.create_program(
            ctypes.byref(program),
            source.encode("utf-8"),
            b"gt1030_probe.cu",
            0,
            None,
            None,
        )
        if result != NVRTC_SUCCESS:
            raise RuntimeError(f"nvrtcCreateProgram failed with error {result}")
        try:
            options = (ctypes.c_char_p * 2)(
                architecture.encode("ascii"), b"--std=c++11"
            )
            with temporary_working_directory(self.root):
                result = self.compile_program(program, len(options), options)
            if result != NVRTC_SUCCESS:
                raise RuntimeError(
                    f"NVRTC compile failed with error {result}: {self._program_log(program)}"
                )
            size = ctypes.c_size_t()
            if self.get_ptx_size(program, ctypes.byref(size)) != NVRTC_SUCCESS:
                raise RuntimeError("nvrtcGetPTXSize failed")
            buffer = ctypes.create_string_buffer(size.value)
            if self.get_ptx(program, buffer) != NVRTC_SUCCESS:
                raise RuntimeError("nvrtcGetPTX failed")
            return bytes(buffer.raw)
        finally:
            self.destroy_program(ctypes.byref(program))

    def _program_log(self, program: ctypes.c_void_p) -> str:
        size = ctypes.c_size_t()
        self.get_log_size(program, ctypes.byref(size))
        if size.value < 2:
            return ""
        buffer = ctypes.create_string_buffer(size.value)
        self.get_log(program, buffer)
        return buffer.value.decode("utf-8", errors="replace")


_KERNEL_SOURCE = r"""
extern "C" __global__ void roi_conv3x3(
    const float* src,
    float* dst,
    int width,
    int height
) {
    int x = blockIdx.x * blockDim.x + threadIdx.x;
    int y = blockIdx.y * blockDim.y + threadIdx.y;
    if (x >= width || y >= height) return;
    float sum = 0.0f;
    for (int dy = -1; dy <= 1; ++dy) {
        int yy = min(max(y + dy, 0), height - 1);
        for (int dx = -1; dx <= 1; ++dx) {
            int xx = min(max(x + dx, 0), width - 1);
            sum += src[yy * width + xx];
        }
    }
    dst[y * width + x] = sum * 0.111111111f;
}
"""
