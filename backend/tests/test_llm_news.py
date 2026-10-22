import llm
import news

RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Big thing happens - The Hindu</title><source>The Hindu</source></item>
<item><title>Another story - BBC News</title></item>
</channel></rss>"""


def test_parse_plain_json():
    p = llm.parse_reply('{"reply":"Opening Chrome.","actions":[{"name":"open_app","args":{"name":"chrome"}}]}')
    assert p["reply"] == "Opening Chrome." and p["actions"][0]["args"] == {"name": "chrome"}


def test_parse_old_single_action_shape():
    p = llm.parse_reply('{"reply":"ok","action":{"name":"lock_pc","params":{}}}')
    assert p["actions"] == [{"name": "lock_pc", "args": {}}]


def test_parse_code_fence_and_plain_text():
    assert llm.parse_reply('```json\n{"reply":"hi","actions":[]}\n```')["reply"] == "hi"
    assert llm.parse_reply("just talking")["reply"] == "just talking"


def test_max_three_actions():
    many = [{"name": "a", "args": {}}] * 6
    import json
    assert len(llm.parse_reply(json.dumps({"reply": "x", "actions": many}))["actions"]) == 3


def test_has_model_matching():
    assert llm._has_model(["moondream:latest"], "moondream")
    assert llm._has_model(["llama3.2:3b"], "llama3.2:3b")
    assert not llm._has_model(["llama3.2:1b"], "llama3.2:3b")


def test_rss_parse():
    items = news.parse_rss(RSS, 5)
    assert items[0] == {"title": "Big thing happens", "source": "The Hindu"}
    assert items[1] == {"title": "Another story", "source": "BBC News"}


def test_news_falls_back_to_rss(monkeypatch):
    monkeypatch.setattr(news.config, "NEWSDATA_KEY", "bad")
    monkeypatch.setattr(news, "_newsdata", lambda *a: (_ for _ in ()).throw(RuntimeError("401")))
    monkeypatch.setattr(news, "_rss", lambda t, n: [{"title": "From RSS", "source": "x"}])
    assert news.headlines()[0]["title"] == "From RSS"
