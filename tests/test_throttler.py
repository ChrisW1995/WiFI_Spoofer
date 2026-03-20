from wifi_cut.throttler import build_pf_rules, build_dnctl_cmds


def test_build_dnctl_cmds():
    cmds = build_dnctl_cmds(pipe_num=1, bandwidth="10Kbit/s")
    assert ["dnctl", "pipe", "1", "config", "bw", "10Kbit/s"] in cmds


def test_build_pf_rules_single_target():
    rules = build_pf_rules(targets=["192.168.50.137"], pipe_num=1)
    assert "192.168.50.137" in rules
    assert "pipe 1" in rules


def test_build_pf_rules_multiple_targets():
    rules = build_pf_rules(targets=["192.168.50.137", "192.168.50.100"], pipe_num=100)
    assert "192.168.50.137" in rules
    assert "192.168.50.100" in rules
    assert "pipe 100" in rules
    assert "pipe 102" in rules
