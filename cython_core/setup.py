import sys

try:
    from setuptools import setup, Extension
    from Cython.Build import cythonize
    extensions = [
        Extension(
            "cython_core.fast_entropy_c",
            ["cython_core/fast_entropy.pyx"],
            extra_compile_args=["-O3"] if sys.platform != "win32" else ["/O2"],
        )
    ]
    setup(
        name="redops_ai_cython",
        ext_modules=cythonize(extensions, language_level="3"),
    )
except ImportError:
    print("[!] Cython/setuptools not installed or C-compiler unavailable. Using pure Python acceleration fallback.")

