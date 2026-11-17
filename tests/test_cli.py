import io
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from sipl.cli import main

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
POWER = str(EXAMPLES / "power.sipl")
GCD = str(EXAMPLES / "gcd.sipl")
DIVISION = str(EXAMPLES / "division.sipl")


def cli(*argv, stdin=None):
    out, err = io.StringIO(), io.StringIO()
    old_stdin = sys.stdin
    if stdin is not None:
        sys.stdin = io.StringIO(stdin)
    try:
        code = main(list(argv), out, err)
    finally:
        sys.stdin = old_stdin
    return code, out.getvalue(), err.getvalue()

def source_file(text):
    directory = tempfile.TemporaryDirectory()
    path = Path(directory.name) / "prog.sipl"
    path.write_text(text, encoding="utf-8")
    return directory, str(path)

def test_check_ok_text():
    code, out, err = cli("check", POWER)
    assert code == 0 and out.startswith("OK") and err == ""


def test_check_ok_json():
    code, out, _ = cli("check", POWER, "--json")
    data = json.loads(out)
    assert code == 0
    assert data["ok"] is True and data["command"] == "check"
    assert data["schema_version"] == 1


def test_check_syntax_error_text():
    code, out, err = cli("check", "-", stdin="begin X := end")
    assert code == 1 and out == ""
    assert "Syntax error at line 1, column 12" in err
    assert "^" in err


def test_check_syntax_error_json():
    code, out, _ = cli("check", "-", "--json", stdin="begin X := end")
    data = json.loads(out)
    assert code == 1 and data["ok"] is False
    error = data["error"]
    assert error["kind"] == "syntax"
    assert (error["line"], error["column"]) == (1, 12)
    assert "number" in error["expected"]

def test_parse_text_shows_tree():
    code, out, _ = cli("parse", POWER)
    assert code == 0
    assert out.startswith("Program")
    assert "While" in out and "Assign target=R" in out


def test_parse_json_has_ast_with_spans():
    code, out, _ = cli("parse", GCD, "--json")
    data = json.loads(out)
    assert code == 0 and data["command"] == "parse"
    ast = data["ast"]
    assert ast["type"] == "Program"
    assert ast["body"]["type"] == "While"
    assert ast["span"]["start_line"] == 1


def test_parse_all_examples():
    for path in (POWER, GCD, DIVISION):
        assert cli("parse", path)[0] == 0


def test_parse_syntax_error_exit_code():
    assert cli("parse", "-", stdin="begin end")[0] == 1


def test_run_power_text():
    code, out, _ = cli("run", POWER, "--set", "X=2", "--set", "Y=5")
    assert code == 0
    assert "R = 32" in out.splitlines()


def test_run_gcd_json():
    code, out, _ = cli("run", GCD, "--set", "M=12", "--set", "N=18", "--json")
    data = json.loads(out)
    assert code == 0 and data["ok"] is True
    assert data["final_state"] == {"M": 6, "N": 6}
    assert data["steps"] > 0


def test_run_division():
    code, out, _ = cli("run", DIVISION, "--set", "X=7", "--set", "Y=2", "--json")
    state = json.loads(out)["final_state"]
    assert code == 0 and state["R"] == 3 and state["X"] == 1


def test_run_accepts_negative_initial_values():
    code, out, _ = cli("run", "-", "--set", "X=-3", "--json",
                       stdin="begin Y := X * 2 end")
    assert code == 0 and json.loads(out)["final_state"] == {"X": -3, "Y": -6}


def test_run_undefined_variable_exit_3():
    code, out, err = cli("run", "-", stdin="begin X := Y end")
    assert code == 3 and out == ""
    assert "Runtime error" in err and "'Y'" in err


def test_run_undefined_variable_json():
    code, out, _ = cli("run", "-", "--json", stdin="begin X := Y end")
    data = json.loads(out)
    assert code == 3 and data["ok"] is False
    assert data["error"]["kind"] == "runtime"
    assert data["error"]["span"]["start_column"] == 12


def test_run_step_limit():
    code, out, _ = cli("run", "-", "--max-steps", "50", "--json",
                       stdin="begin while 1 > 0 do skip end")
    data = json.loads(out)
    assert code == 3 and data["error"]["kind"] == "step_limit"
    assert data["state"] == {}


def test_run_bad_set_option():
    code, out, err = cli("run", POWER, "--set", "X")
    assert code == 2 and "VAR=INT" in err


def test_run_bad_set_option_json():
    code, out, _ = cli("run", POWER, "--set", "1X=5", "--json")
    data = json.loads(out)
    assert code == 2 and data["error"]["kind"] == "usage"


def test_trace_text_lines():
    code, out, _ = cli("trace", "-", stdin="begin X := 1 end")
    lines = out.splitlines()
    assert code == 0
    assert lines[0].startswith("start")
    assert "X: undefined -> 1" in out
    assert lines[-1].startswith("finished: ok")


def test_trace_json_schema():
    code, out, _ = cli("trace", POWER, "--set", "X=2", "--set", "Y=3", "--json")
    data = json.loads(out)
    assert code == 0
    assert set(data) == {"schema_version", "command", "ok", "status",
                         "final_state", "events"}
    assert data["status"] == "ok" and data["final_state"]["R"] == 8
    kinds = {e["type"] for e in data["events"]}
    assert kinds == {"program_started", "before_statement", "after_statement",
                     "variable_changed", "condition_evaluated", "program_finished"}


def test_trace_error_still_prints_trace_and_exit_3():
    code, out, _ = cli("trace", "-", "--json", stdin="begin X := 1; Y := Z end")
    data = json.loads(out)
    assert code == 3 and data["ok"] is False
    assert data["status"] == "error"
    assert data["error"]["kind"] == "runtime"
    assert data["events"][-1]["type"] == "program_finished"
    assert data["final_state"] == {"X": 1}


def test_trace_step_limit_json():
    code, out, _ = cli("trace", "-", "--max-steps", "5", "--json",
                       stdin="begin while 1 > 0 do skip end")
    data = json.loads(out)
    assert code == 3 and data["error"]["kind"] == "step_limit"

def test_missing_file_exit_2():
    code, out, err = cli("check", "no_such_file.sipl")
    assert code == 2 and "cannot read" in err


def test_missing_file_json():
    code, out, _ = cli("run", "no_such_file.sipl", "--json")
    data = json.loads(out)
    assert code == 2 and data["error"]["kind"] == "io"


def test_no_command_is_usage_error():
    assert cli()[0] == 2


def test_unknown_command_is_usage_error():
    assert cli("explode", POWER)[0] == 2


def test_help_exits_zero():
    assert cli("--help")[0] == 0


def test_json_mode_prints_one_json_document():
    _, out, _ = cli("trace", GCD, "--set", "M=4", "--set", "N=6", "--json")
    json.loads(out)


def test_reads_file_from_disk_with_unicode_operators():
    directory, path = source_file("begin if ¬ X = 1 ∨ X > 5 then Y := 1 else Y := 0 end")
    with directory:
        code, out, _ = cli("run", path, "--set", "X=2", "--json")
    assert code == 0 and json.loads(out)["final_state"]["Y"] == 1

def test_module_entry_point_as_subprocess():
    result = subprocess.run([sys.executable, "-m", "sipl", "run", POWER,
                             "--set", "X=3", "--set", "Y=2", "--json"],
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert json.loads(result.stdout)["final_state"]["R"] == 9


def test_subprocess_exit_code_for_syntax_error():
    result = subprocess.run([sys.executable, "-m", "sipl", "check", "-"],
                            input="begin end", capture_output=True, text=True)
    assert result.returncode == 1

def test_term_text_for_power_matches_the_practicum():
    code, out, _ = cli("term", POWER)
    assert code == 0
    assert out.strip() == ("AS_R(1) · WH(S²(gr, Y⇒, 0), "
                           "AS_R(S²(mult, R⇒, X⇒)) · AS_Y(S²(sub, Y⇒, 1)))")


def test_term_ascii_style():
    code, out, _ = cli("term", POWER, "--style", "ascii")
    assert code == 0 and out.strip().isascii()
    assert out.strip().startswith("AS_R(1) ; WH(S2(gr, Y=>, 0)")


def test_term_json():
    code, out, _ = cli("term", GCD, "--json")
    data = json.loads(out)
    assert code == 0 and data["command"] == "term" and data["ok"] is True
    assert data["term"]["type"] == "WH"
    assert data["text"].startswith("WH(S¹(neg")
    assert "steps" not in data


def test_term_steps_text_and_json():
    code, out, _ = cli("term", POWER, "--steps")
    lines = out.splitlines()
    assert code == 0 and lines[1].strip().startswith("NS_Prog")
    code, out, _ = cli("term", POWER, "--steps", "--json")
    steps = json.loads(out)["steps"]
    assert steps[0]["rule"] == "NS_Prog" and steps[0]["span"]["start_line"] == 1
    assert [s["rule"] for s in steps].count("NS_Stm_As") == 3


def test_term_syntax_error_exit_code():
    code, out, err = cli("term", "-", stdin="begin X := end")
    assert code == 1 and "Syntax error" in err


def test_term_bad_style_is_usage_error():
    assert cli("term", POWER, "--style", "latex")[0] == 2


def test_apply_power_text():
    code, out, _ = cli("apply", POWER, "--set", "X=2", "--set", "Y=5")
    assert code == 0
    assert out.splitlines() == ["R = 32", "X = 2", "Y = 0"]


def test_apply_steps_prints_trace_then_state():
    code, out, _ = cli("apply", POWER, "--set", "X=2", "--set", "Y=1", "--steps")
    lines = out.splitlines()
    assert code == 0 and lines[0].startswith("AF_SEQ")
    assert "AF_WH" in out and lines[-1] == "Y = 0"
    assert "↦" in out


def test_apply_ascii_style():
    code, out, _ = cli("apply", POWER, "--set", "X=2", "--set", "Y=1",
                       "--steps", "--style", "ascii")
    assert code == 0 and "->" in out and "↦" not in out


def test_apply_undefined_variable_exit_3():
    code, out, err = cli("apply", "-", stdin="begin X := Y end")
    assert code == 3 and out == ""
    assert err.startswith("undefined:") and "'Y'" in err


def test_apply_undefined_loop_step_limit():
    code, _, err = cli("apply", "-", "--max-steps", "50",
                       stdin="begin while 1 > 0 do X := 1 end")
    assert code == 3 and "step limit" in err


def test_apply_json_defined():
    code, out, _ = cli("apply", POWER, "--set", "X=2", "--set", "Y=2", "--json", "--steps")
    data = json.loads(out)
    assert code == 0 and data["ok"] is True and data["command"] == "apply"
    assert data["status"] == "defined"
    assert data["final_state"] == {"X": 2, "Y": 0, "R": 4}
    assert data["steps"][0]["formula"] == "AF_SEQ"


def test_apply_json_without_steps_has_no_trace():
    _, out, _ = cli("apply", POWER, "--set", "X=2", "--set", "Y=2", "--json")
    assert "steps" not in json.loads(out)


def test_apply_json_undefined():
    code, out, _ = cli("apply", "-", "--json", stdin="begin X := Y end")
    data = json.loads(out)
    assert code == 3 and data["ok"] is False and data["status"] == "undefined"
    assert data["final_state"] is None
    assert data["error"]["kind"] == "undefined"


def test_apply_agrees_with_run():
    _, a, _ = cli("apply", POWER, "--set", "X=3", "--set", "Y=3")
    _, r, _ = cli("run", POWER, "--set", "X=3", "--set", "Y=3")
    assert a == r


def test_apply_syntax_error_exit_code():
    code, _, err = cli("apply", "-", stdin="begin X := end")
    assert code == 1