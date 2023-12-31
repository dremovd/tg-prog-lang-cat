#!/usr/bin/env python3
"""
Build script. Performs shared library build, links it with tester binary and finaly builds tester binary.
"""

import argparse
import os
import shutil
import logging
import zipfile
import glob
from subprocess import check_call


DEFAULT_SOURCE_PATH = os.path.dirname(os.path.abspath(__file__))
DEFAULT_BUILD_PATH = os.path.join(DEFAULT_SOURCE_PATH, "build")

LIB_BINARY_NAME = "libtglang.so"
TESTER_BINARY_NAME = "tglang-tester"
MULTITESTER_BINARY_NAME = "tglang-multitester"
RUNNER_BINARY_NAME = "run-tglang.py"

FASTTEXT_MODEL_FNAME = "fasttext-model.bin"
DEP_PACKAGES_FNAME = "deb-packages.txt"

BINARY_DIR = "bin"

RESOURCES_DIR = "resources"

LIB_TARGET = "libtglang"
TESTER_TARGET = "tglang-tester"
MULTITESTER_TARGET = "tglang-multitester"
LINK_TESTER_TARGET = "link-tester"
LINK_MULTITESTER_TARGET = "link-multitester"
TESTFILE_TARGET = "test_file"
BINARY_TARGET = "binary"
CREATE_SUBMISSION_TARGET = "create-submission"


AVAILABLE_TARGETS = (
    LIB_TARGET,
    TESTER_TARGET,
    BINARY_TARGET,
    TESTFILE_TARGET,
    CREATE_SUBMISSION_TARGET,
)


def main():
    logging.getLogger().setLevel(logging.INFO)
    
    args = parse_args()
    if args.clean and os.path.exists(args.build_dir):
        shutil.rmtree(args.build_dir)
    
    targets = set(args.target)
    
    if CREATE_SUBMISSION_TARGET in targets:
        logging.warning("Force set build-type to `Release`, creating submission")
        args.build_type = "Release"
    
    context = {
        "build_type": args.build_type,
        "build_dir": args.build_dir,
        "source_dir": args.source_dir,
        "test_file": args.test_file,
        "bin_dir": os.path.join(args.build_dir, BINARY_DIR),
    }
    
    visited = set()
    def traverse(target):
        if target in visited:
            return
        visited.add(target)
        
        for dep in DEPENDENCIES[target]:
            traverse(dep)
        
        logging.info("Begin to exec target: `%s`", target);
        ACTIONS[target](target, context)
    
    if args.test_file:
        targets.add(TESTFILE_TARGET)
        binary_exists = os.path.exists(os.path.join(context["build_dir"], TESTER_TARGET, TESTER_BINARY_NAME))
        if BINARY_TARGET not in targets and not binary_exists:
            targets.add(TESTFILE_TARGET)
    
    for t in targets:
        traverse(t)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        help="Targets to build",
        choices=AVAILABLE_TARGETS,
        default=[BINARY_TARGET],
        nargs="*",
    )
    parser.add_argument(
        "--clean",
        help="Remove cmake config dir to rebuild project from scratch",
        default=False,
        action="store_true",
    )
    parser.add_argument(
        "-b,",
        "--build-type",
        help="Build type",
        choices=("Release", "RelWithDebInfo", "Debug"),
        default="Debug",
    )
    parser.add_argument(
        "-S", 
        "--source-dir", 
        default=DEFAULT_SOURCE_PATH, 
        help="Project source directory"
    )
    parser.add_argument(
        "-B",
        "--build-dir",
        default=DEFAULT_BUILD_PATH,
        help="Cmake build directory, stores CMake generated output and build artficats",
    )
    parser.add_argument(
        "-t",
        "--test-file",
        help="Cmake build directory, stores CMake generated output and build artficats",
    )

    return parser.parse_args()


def build_target(target, context):
    build_dir = os.path.join(context["build_dir"], target)
    source_dir = os.path.join(context["source_dir"], "src", target)
    for d in build_dir, source_dir:
        if not os.path.exists(d):
            os.makedirs(d)

    check_call(["cmake", f"-DCMAKE_BUILD_TYPE={context['build_type']}", "-S", source_dir, "-B", build_dir])
    check_call(["cmake", "--build", build_dir, "--parallel"])


def link_tester(_target, context):
    src = os.path.join(context["build_dir"], LIB_TARGET, LIB_BINARY_NAME)
    dst = os.path.join(context["source_dir"], "src", TESTER_TARGET, LIB_BINARY_NAME)
    try:
        # can't detect wiether dst exists without exception, so remove it in anycase and ignore exception
        os.remove(dst)
    except FileNotFoundError:
        pass

    os.symlink(src=src, dst=dst)


def link_multitester(_target, context):
    src = os.path.join(context["build_dir"], LIB_TARGET, LIB_BINARY_NAME)
    dst = os.path.join(context["source_dir"], "src", MULTITESTER_TARGET, LIB_BINARY_NAME)
    try:
        # can't detect wiether dst exists without exception, so remove it in anycase and ignore exception
        os.remove(dst)
    except FileNotFoundError:
        pass

    os.symlink(src=src, dst=dst)


def run_tester(_target, context):
    binary = os.path.join(context["bin_dir"], TESTER_BINARY_NAME)
    if not os.path.exists(binary):
        raise RuntimeError(f"Binary doesn't exists: `{binary}`")
    check_call([binary, context["test_file"]], env={"LD_LIBRARY_PATH": context["bin_dir"]}, cwd=context["bin_dir"])


def copy_binaries(_target, context):
    tester = os.path.join(context["build_dir"], TESTER_TARGET, TESTER_BINARY_NAME)
    multitester = os.path.join(context["build_dir"], MULTITESTER_TARGET, MULTITESTER_BINARY_NAME)
    lib = os.path.join(context["build_dir"], LIB_TARGET, LIB_BINARY_NAME)
    runner = os.path.join(DEFAULT_SOURCE_PATH, "scripts", RUNNER_BINARY_NAME)
    bin_targets = [tester, multitester, lib, runner]
    
    fasttext_model = os.path.join(context["source_dir"], "src", RESOURCES_DIR, FASTTEXT_MODEL_FNAME)
    resource_targets = [fasttext_model]

    for f in bin_targets + resource_targets:
        if not os.path.exists(f):
            raise RuntimeError(f"No binary file: `{f}`")
    
    bin_dir = context["bin_dir"]
    try:
        shutil.rmtree(bin_dir)
    except FileNotFoundError:
        pass
    os.makedirs(bin_dir)

    for f in bin_targets:
        shutil.copy(f, os.path.join(bin_dir, os.path.basename(f)))
    
    resources_dir = os.path.join(bin_dir, RESOURCES_DIR)
    os.makedirs(resources_dir)
    for f in resource_targets:
        shutil.copy(f, os.path.join(resources_dir, os.path.basename(f)))


def create_submission(_target, context):
    submission_fpath = os.path.join(context["bin_dir"], "submission.zip")
    libsrc_dir = os.path.join(context["source_dir"], "src", LIB_TARGET)
    pattern = os.path.join(libsrc_dir, "**")
    to_ignore = [os.path.join(libsrc_dir, v) for v in ("build", "fasttext_model_blob.h")]
    
    to_archive = [
        (os.path.join(context["bin_dir"], LIB_BINARY_NAME), LIB_BINARY_NAME),   
        (os.path.join(context["source_dir"], "src", DEP_PACKAGES_FNAME), DEP_PACKAGES_FNAME),   
    ]
    
    for src_path in glob.glob(pattern, recursive=True):
        assert(src_path.startswith(libsrc_dir))
        
        if os.path.isdir(src_path):
            continue
        
        skip = False
        for ignore in to_ignore:
            if src_path.startswith(ignore):
                skip = True
                break
        if skip:
            continue
        
        dst_path = src_path[len(libsrc_dir):]
        if dst_path.startswith("/"):
            dst_path = dst_path[1:]
        dst_path = os.path.join("src", dst_path)
            
        to_archive.append((src_path, dst_path))
    
    resources_dir = os.path.join(context["bin_dir"], RESOURCES_DIR)
    resources_pattern = os.path.join(resources_dir, "**")
    for src_path in glob.glob(resources_pattern, recursive=True):
        assert(src_path.startswith(resources_dir))
        if os.path.isdir(src_path):
            continue
        
        dst_path = src_path[len(resources_dir):]
        if dst_path.startswith("/"):
            dst_path = dst_path[1:]
        dst_path = os.path.join(RESOURCES_DIR, dst_path)
        to_archive.append((src_path, dst_path))
    
    with zipfile.ZipFile(submission_fpath, "w") as arch:
        for src_path, dst_path in to_archive:
            with arch.open(dst_path, "w") as dst, open(src_path, "rb") as src:
                dst.write(src.read())
                
        
DEPENDENCIES = {
    TESTER_TARGET: [LINK_TESTER_TARGET],
    MULTITESTER_TARGET: [LINK_MULTITESTER_TARGET],
    LINK_TESTER_TARGET: [LIB_TARGET],
    LINK_MULTITESTER_TARGET: [LIB_TARGET],
    LIB_TARGET: [],
    BINARY_TARGET: [TESTER_TARGET, MULTITESTER_TARGET, LIB_TARGET],
    TESTFILE_TARGET: [BINARY_TARGET],
    CREATE_SUBMISSION_TARGET: [BINARY_TARGET],
}


ACTIONS = {
    TESTER_TARGET: build_target,
    MULTITESTER_TARGET: build_target,
    LINK_TESTER_TARGET: link_tester,
    LINK_MULTITESTER_TARGET: link_multitester,
    LIB_TARGET: build_target,
    BINARY_TARGET: copy_binaries,
    TESTFILE_TARGET: run_tester,
    CREATE_SUBMISSION_TARGET: create_submission, 
}


if __name__ == "__main__":
    main()
