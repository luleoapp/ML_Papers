"""Setup for C++ extension module."""

from setuptools import setup, Extension
from setuptools.command.build_ext import build_ext
import os
import sys
import tempfile
import subprocess
import platform


class CMakeExtension(Extension):
    """Extension for CMake-based build."""
    
    def __init__(self, name, sourcedir=""):
        Extension.__init__(self, name, sources=[])
        self.sourcedir = os.path.abspath(sourcedir)


class CMakeBuild(build_ext):
    """Custom build command for CMake-based build."""
    
    def run(self):
        """Run the build command."""
        for ext in self.extensions:
            self.build_extension(ext)
    
    def build_extension(self, ext):
        """Build the extension."""
        extdir = os.path.abspath(os.path.dirname(self.get_ext_fullpath(ext.name)))
        
        cmake_args = [
            f"-DCMAKE_LIBRARY_OUTPUT_DIRECTORY={extdir}",
            f"-DPYTHON_EXECUTABLE={sys.executable}",
            "-DCMAKE_BUILD_TYPE=Release"
        ]
        
        build_args = ["--config", "Release"]
        
        # Detect platform-specific settings
        if platform.system() == "Windows":
            cmake_args += ["-DCMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE={}".format(extdir)]
            build_args += ["--", "/m"]
        else:
            build_args += ["--", "-j4"]
        
        # Create build directory
        os.makedirs(self.build_temp, exist_ok=True)
        
        # Configure and build
        subprocess.check_call(
            ["cmake", ext.sourcedir] + cmake_args, 
            cwd=self.build_temp
        )
        subprocess.check_call(
            ["cmake", "--build", "."] + build_args, 
            cwd=self.build_temp
        )


setup(
    name="backtest_engine",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="C++ backtest engine with Python bindings",
    long_description="""
        C++ backtest engine for processing tick data with Python bindings.
    """,
    ext_modules=[CMakeExtension("backtest_simulator.cpp.backtest_engine")],
    cmdclass={"build_ext": CMakeBuild},
    zip_safe=False,
)
