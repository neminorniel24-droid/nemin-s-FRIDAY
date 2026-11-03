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


def test_max_six_actions():
    many = [{"name": "a", "args": {}}] * 9
    import json
    assert len(llm.parse_reply(json.dumps({"reply": "x", "actions": many}))["actions"]) == 6


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


def test_vision_falls_back_when_model_is_retired(monkeypatch):
    import config
    monkeypatch.setattr(config, "GROQ_API_KEY", "k")
    monkeypatch.setattr(config, "GROQ_VISION_MODEL", "meta-llama/retired")
    monkeypatch.setattr(config, "LLM_PROVIDER", "groq")
    tried = []

    class FakeCompletions:
        def create(self, model, **kw):
            tried.append(model)
            if model == "meta-llama/retired":
                raise Exception("Error code: 404 - model_not_found")
            msg = type("M", (), {"content": "a red cup"})()
            return type("R", (), {"choices": [type("C", (), {"message": msg})()]})()
    fake = type("G", (), {"chat": type("Ch", (), {"completions": FakeCompletions()})()})()
    monkeypatch.setattr(llm, "_groq", lambda: fake)
    text, provider = llm.describe_image("data:image/jpeg;base64,AAAA", "what is this")
    assert text == "a red cup" and provider == "groq" and tried == ["meta-llama/retired", "qwen/qwen3.8-27b"]
