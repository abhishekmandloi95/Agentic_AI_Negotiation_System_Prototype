import pytest

@pytest.mark.ui
def test_baseline_ui_run_and_rerun(tmp_path, monkeypatch):
    from streamlit.testing.v1 import AppTest
    from utils.paths import ROOT
    import utils.history_store as store
    monkeypatch.setattr(store, "DATA_DIR", tmp_path)
    monkeypatch.setattr(store, "HISTORY_FILE", tmp_path / "trades.json")
    app = AppTest.from_file(str(ROOT / "ui_app.py"), default_timeout=30).run()
    assert not app.exception
    app.selectbox[0].select("Deterministic baseline").run()
    next(b for b in app.button if b.label == "Start Negotiation").click().run()
    assert not app.exception and not app.error
    records = app.session_state["current_contracts"]
    assert records and all(record["status"] == "executed" for record in records)
    assert len(store.load_trade_history()) == len(records)
    assert app.session_state["metrics"]
    app.run()
    assert len(store.load_trade_history()) == len(records)
    assert not app.exception
