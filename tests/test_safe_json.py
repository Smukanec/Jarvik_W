import subprocess
import textwrap


def test_safe_json_html():
    script = textwrap.dedent("""
    async function safeJson(res) {
      const txt = await res.text();
      try {
        return JSON.parse(txt);
      } catch (_) {
        throw new Error('Server returned invalid response');
      }
    }
    (async () => {
      const res = new Response('<html></html>', {headers:{'Content-Type':'text/html'}});
      try { await safeJson(res); } catch (e) { console.log(e.message); }
    })();
    """)
    out = subprocess.check_output(["node", "-e", script], text=True).strip()
    assert out == "Server returned invalid response"
