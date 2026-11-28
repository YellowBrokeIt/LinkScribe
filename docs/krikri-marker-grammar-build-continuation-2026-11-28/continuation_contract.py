"""Read-only verification of the one retained build and exact system headers."""
from pathlib import Path
import shlex

from context import HERE, ROOT, OWNED, NATIVE_PLAN, read, record, sha


def require_record(value):
    path = Path(value["path"])
    if path.is_symlink() or path.stat().st_size != value["bytes"] or sha(path) != value["sha256"]:
        raise ValueError("Retained artifact changed: " + str(path))
    return path


def require_successful_command(value, argv, environment, cwd):
    if (value.get("complete") is not True or value.get("exit_code") != 0
            or value.get("argv") != argv or value.get("environment") != environment
            or value.get("cwd") != cwd):
        raise ValueError("Retained command did not complete under its exact frozen invocation.")
    if set(value.get("raw_streams", {})) != {"stdout", "stderr"}:
        raise ValueError("Retained command lacks both full output streams.")
    for stream in value["raw_streams"].values():
        require_record(stream)
    if value["raw_streams"]["stderr"]["bytes"]:
        raise ValueError("The retained successful setup command has unexpected stderr.")


def require_phase_resources(report, resources, samples_path, expected_success):
    if (report.get("complete") is not expected_success
            or resources.get("complete") is not expected_success
            or resources.get("passed") is not expected_success
            or resources.get("measurement_complete") is not True
            or resources.get("owned_processes_stopped") is not True
            or resources.get("measurement_errors")
            or resources.get("phase_time_limit_exceeded") is not False
            or resources.get("stop_reason") or resources.get("error")
            or resources.get("elapsed_seconds", float("inf")) > resources["limits"]["total_seconds"]
            or resources.get("samples_sha256") != sha(samples_path)):
        raise ValueError("Previous phase lacks its exact observed resource/cleanup disposition.")
    if resources["worker_exit_code"] != (0 if expected_success else 1):
        raise ValueError("Previous phase exit code differs from its frozen outcome.")


def verify_prior_stage():
    bound = read(HERE / "continuation-inputs.json")
    previous = Path(bound["previous_directory"])
    for row in bound["retained_files"]:
        require_record(row)
    reports = {}
    resources = {}
    for phase, success in [("acquire", True), ("build", False)]:
        report = read(previous / (phase + ".json"))
        resource = read(previous / (phase + "-resources.json"))
        if (resource["phase_report_sha256"] != sha(previous / (phase + ".json"))
                or resource["plan_sha256"] != bound["previous_plan_sha256"]
                or report["plan_sha256"] != bound["previous_plan_sha256"]
                or report["authorization_sha256"] != sha(previous / (phase + "-authorization.json"))
                or report["claim_sha256"] != sha(previous / (phase + "-claim.json"))):
            raise ValueError("Prior source/phase authorization binding differs.")
        require_phase_resources(report, resource, previous / resource["samples_file"], success)
        reports[phase], resources[phase] = report, resource
    failed = reports["build"]
    if (failed.get("error") != bound["expected_prior_build_error"] or "sanity" in failed
            or failed.get("generation_calls") != 0 or failed.get("network_model_downloads") != 0):
        raise ValueError("The retained build failed at a different stage or already ran sanity probes.")
    total = sum(row["elapsed_seconds"] for row in resources.values())
    if total != bound["carried_active_seconds"] or resources["build"]["elapsed_seconds"] != bound["spent_build_seconds"]:
        raise ValueError("Prior measured time was not carried forward exactly.")
    command = read(NATIVE_PLAN / "build-command.json")
    for key, argv in [("compile_receipt", command["argv"]),
                      ("elf_receipt", command["post_link_elf_read_argv"]),
                      ("loader_receipt", command["post_link_loader_list_argv"])]:
        receipt_path = require_record(failed[key])
        require_successful_command(read(receipt_path), argv, command["environment_allowlist"], command["cwd"])
    require_record(failed["validator"])
    require_record(failed["compiler_dependency_file"])
    if (failed["validator"] != bound["validator"]
            or failed["compiler_dependency_file"] != bound["depfile"]):
        raise ValueError("The exact retained compiled artifact or dependency receipt differs.")
    return {"carried_active_seconds": total, "spent_build_seconds": resources["build"]["elapsed_seconds"],
            "prior_build_report": failed, "prior_acquire_report": reports["acquire"],
            "prior_build_report_record": record(previous / "build.json"),
            "prior_build_resource_record": record(previous / "build-resources.json")}


def verify_exact_dependencies(profile=None):
    if profile is None:
        profile = read(HERE / "independent-prior-stage-review/actual-header-dependencies.json")
    depfile = require_record(profile["depfile"])
    target, separator, remainder = depfile.read_text().replace("\\\n", " ").partition(":")
    binary = OWNED / "bin/test-gbnf-validator"
    if not separator or shlex.split(target) != [str(binary)]:
        raise ValueError("Retained compiler dependency target differs.")
    names = shlex.split(remainder)
    rows = profile["all_dependencies"]
    if (len(names) != len(set(names)) or len(names) != profile["dependency_count"]
            or len(names) != 273 or names != [row["compiler_path"] for row in rows]):
        raise ValueError("Retained compiler dependency membership/order differs.")
    exceptions = profile["unexpected_resolved_headers"]
    if len(exceptions) != 5 or len({row["path"] for row in exceptions}) != 5:
        raise ValueError("Exactly the five independently observed system-header aliases are required.")
    exception_map = {row["path"]: row for row in exceptions}
    allowed = (OWNED / "source", Path("/usr/include"), Path("/usr/lib/gcc"), Path("/usr/libexec/gcc"))
    observed_exceptions = set()
    observed = []
    for name, row in zip(names, rows):
        path = Path(name).resolve(strict=True)
        if str(path) != row["path"]:
            raise ValueError("Retained dependency resolves differently: " + name)
        require_record(row)
        ordinarily_allowed = any(path.is_relative_to(root) for root in allowed)
        if row["allowed_by_original_gate"] is not ordinarily_allowed:
            raise ValueError("Original dependency-gate classification differs.")
        if not ordinarily_allowed:
            exception = exception_map.get(str(path))
            if not exception or any(exception[key] != row[key] for key in ["path", "bytes", "sha256", "compiler_path"]):
                raise ValueError("An out-of-root dependency is not one of the exact five bound files.")
            alias = exception["system_include_alias"]
            alias_path = Path(alias["path"])
            if (not alias_path.is_symlink() or not alias_path.is_relative_to(Path("/usr/include"))
                    or alias_path.readlink().as_posix() != alias["link_text"]
                    or str(alias_path.resolve(strict=True)) != alias["resolved"]
                    or alias["resolved"] != str(path)):
                raise ValueError("The bound system include alias differs.")
            observed_exceptions.add(str(path))
        observed.append(record(path))
    if observed_exceptions != set(exception_map):
        raise ValueError("A bound system-header exception is absent or unused.")
    return observed
