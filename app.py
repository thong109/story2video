"""Giao dien web nho cho story2video. Chay: python app.py"""
import json
import os
import secrets
import re
import shutil
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.request
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file, abort

ROOT = Path(__file__).parent.resolve()
SETTINGS_PATH = ROOT / "local_settings.json"
app = Flask(__name__)
JOBS = {}
LOCK = threading.Lock()
SETTINGS_LOCK = threading.Lock()


def read_local_settings():
    try:
        value = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def active_ai_settings():
    local = read_local_settings()
    if local.get("provider") == "ollama":
        return {"provider": "ollama", "api_key": "", "model": local.get("model", "qwen2.5:7b"),
                "base_url": local.get("base_url", "http://localhost:11434")}
    if local.get("api_key"):
        return {"provider": local.get("provider", "muse"), "api_key": local["api_key"],
                "model": local.get("model", "muse-spark-1.3"), "base_url": ""}
    hf_token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACEHUB_API_TOKEN")
    if hf_token:
        return {"provider": "huggingface", "api_key": hf_token,
                "model": os.environ.get("HF_MODEL", "Qwen/Qwen2.5-7B-Instruct-1M:fastest"), "base_url": ""}
    muse_key = os.environ.get("MODEL_API_KEY") or os.environ.get("MUSE_API_KEY")
    if muse_key:
        return {"provider": "muse", "api_key": muse_key, "model": os.environ.get("MUSE_MODEL", "muse-spark-1.3"), "base_url": ""}
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        return {"provider": "anthropic", "api_key": anthropic_key, "model": os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5"), "base_url": ""}
    provider = local.get("provider", "muse")
    return {"provider": provider, "api_key": "",
            "model": local.get("model", "muse-spark-1.3" if provider == "muse" else "claude-sonnet-5-5"), "base_url": ""}


def character_records():
    cast_path = ROOT / "assets" / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else {}
    job_names = {"doctor": "Bác sĩ", "chef": "Đầu bếp", "police": "Công an", "artist": "Họa sĩ",
                 "office": "Nhân viên văn phòng", "teacher": "Giáo viên", "engineer": "Kỹ sư", "farmer": "Nông dân", "daoist": "Đạo sĩ"}
    kind_names = {"human": "Người", "dog": "Chó", "cat": "Mèo", "crocodile": "Cá sấu", "ghost": "Ma"}
    records = []
    for cid, spec in cast.items():
        folder = ROOT / "assets" / "characters" / cid
        if (folder / "neutral.png").exists():
            records.append({"id": cid, "name": spec.get("name", cid.replace("_", " ").title()),
                            "gender": spec.get("gender", "nam"), "age": spec.get("age", ""),
                            "kind": kind_names.get(spec.get("kind", "human"), "Người"),
                            "job": job_names.get(spec.get("job", ""), ""), "description": spec.get("description", ""),
                            "image": f"/api/characters/{cid}/image"})
    return records

PAGE = r'''<!doctype html>
<html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Story Studio — Truyện thành phim</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--ink:#1d2927;--muted:#79817d;--paper:#f6f5f0;--white:#fff;--line:#e8e8e0;--green:#256b50;--lime:#c8e5a2;--orange:#ef8354;--soft:#eaf1e8;--shadow:0 12px 35px #20352b0c}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font:14px 'DM Sans',sans-serif}button,input,textarea,select{font:inherit}button{cursor:pointer}.layout{min-height:100vh;display:grid;grid-template-columns:244px 1fr}.side{background:#fbfaf6;border-right:1px solid var(--line);padding:25px 17px;display:flex;flex-direction:column;gap:27px}.brand{display:flex;align-items:center;gap:11px;padding:0 8px;font:800 17px Manrope}.brandmark{width:36px;height:36px;background:var(--green);border-radius:12px;display:grid;place-items:center;color:#fff;font-size:18px}.brand small{display:block;color:var(--muted);font:500 10px 'DM Sans';margin-top:2px}.nav-label{padding:0 10px;color:#a0a6a0;text-transform:uppercase;letter-spacing:1.1px;font-size:10px;font-weight:700;margin-bottom:7px}.nav{display:grid;gap:4px}.nav button{border:0;background:none;text-align:left;padding:11px 12px;border-radius:10px;color:#67726c;display:flex;gap:11px;align-items:center}.nav button.active{background:#eaf1e8;color:var(--green);font-weight:700}.nav .ico{width:19px;font-size:16px;text-align:center}.project{background:#f0f3eb;border-radius:14px;padding:14px;margin-top:auto}.project b{font-size:12px}.project p{margin:7px 0 0;color:#788277;font-size:11px;line-height:1.5}.main{min-width:0}.topbar{height:72px;border-bottom:1px solid var(--line);display:flex;align-items:center;justify-content:space-between;padding:0 38px;background:#fbfaf7}.crumb{color:var(--muted)}.crumb b{color:var(--ink);font-weight:600}.status{display:flex;align-items:center;gap:8px;color:#657168;font-size:12px}.dot{width:7px;height:7px;background:#65aa72;border-radius:50%}.content{max-width:1260px;margin:auto;padding:32px 38px 60px}.heading{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:25px}.eyebrow{color:var(--green);font-size:11px;font-weight:700;letter-spacing:1.4px;text-transform:uppercase}.heading h1{font:800 clamp(27px,3vw,36px) Manrope;margin:8px 0 5px;letter-spacing:-1.3px}.heading p{margin:0;color:var(--muted)}.stepper{display:flex;align-items:center;gap:9px;color:#858c86;font-size:11px}.step{display:flex;align-items:center;gap:6px}.step i{font-style:normal;border:1px solid #daddd5;width:23px;height:23px;display:grid;place-items:center;border-radius:50%;font-size:10px}.step.on{color:var(--green);font-weight:700}.step.on i{background:var(--green);border-color:var(--green);color:white}.sep{color:#c5c9c1}.workspace{display:grid;grid-template-columns:minmax(390px,1fr) minmax(330px,.78fr);gap:20px;align-items:start}.card{background:var(--white);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow)}.input-card{padding:22px}.card-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:17px}.card-title h2{font:700 16px Manrope;margin:0;letter-spacing:-.3px}.hint{font-size:11px;color:var(--muted)}.label{display:flex;justify-content:space-between;align-items:center;font-weight:700;font-size:12px;margin:17px 0 8px}.label span{font-weight:400;color:#98a098;font-size:11px}.title-input,textarea{width:100%;border:1px solid #e5e8e1;border-radius:10px;background:#fdfdfb;padding:12px 13px;color:var(--ink);outline:none;transition:.2s}.title-input:focus,textarea:focus{border-color:#8cad8e;box-shadow:0 0 0 3px #256b5010}.title-input{height:43px}textarea{height:266px;resize:vertical;line-height:1.7;font-size:13px}.toolbar{display:flex;justify-content:space-between;align-items:center;margin-top:8px;color:#939b94;font-size:11px}.examples{display:flex;gap:7px}.examples button{border:1px solid #e5e8e1;background:#fff;border-radius:7px;padding:6px 9px;color:#667069;font-size:10px}.examples button:hover{border-color:#a4b99e;color:var(--green)}.actions{display:flex;gap:9px;margin-top:19px}.btn{border:0;border-radius:9px;padding:11px 14px;font-weight:700;font-size:12px;display:inline-flex;gap:8px;align-items:center;justify-content:center}.btn-primary{background:var(--green);color:white;flex:1;box-shadow:0 4px 10px #256b5021}.btn-primary:hover{background:#1d5942}.btn-secondary{background:#f0f2ec;color:#47534a}.right{display:grid;gap:17px}.preview{overflow:hidden}.preview-head{padding:17px 18px 13px;display:flex;justify-content:space-between;align-items:center}.preview-head b{font:700 14px Manrope}.preview-stage{margin:0 14px;background:#dfe8dc;border-radius:11px;aspect-ratio:16/9;position:relative;overflow:hidden;display:grid;place-items:center}.preview-stage img{width:100%;height:100%;object-fit:cover}.placeholder{text-align:center;color:#748277}.placeholder .clapper{font-size:30px;margin-bottom:8px}.placeholder b{display:block;font-size:12px;color:#46554a}.placeholder small{display:block;font-size:10px;margin-top:4px}.stage-tag{position:absolute;left:11px;top:11px;background:#ffffffd9;padding:6px 8px;border-radius:7px;font-size:10px;color:#536156}.preview-foot{padding:13px 17px 16px;display:flex;justify-content:space-between;align-items:center}.preview-foot small{color:var(--muted);font-size:10px}.duration{color:#5a655d;font-size:11px;font-weight:600}.details{padding:17px 18px}.details h3{font:700 13px Manrope;margin:0 0 14px}.chips{display:flex;gap:7px;flex-wrap:wrap}.chip{background:#f2f4ef;border-radius:7px;padding:7px 9px;color:#647067;font-size:10px}.chip strong{color:#35483a}.voice{margin-top:15px;border-top:1px solid #eff0eb;padding-top:13px;display:flex;justify-content:space-between;color:#727b74;font-size:11px}.voice b{color:#35483a}.tip{padding:13px 15px;background:#f0f4e9;border-radius:12px;color:#66725f;font-size:11px;line-height:1.55}.tip strong{color:#3c5b3c}.toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:#26362c;color:white;padding:12px 17px;border-radius:10px;box-shadow:var(--shadow);z-index:4;display:none;max-width:90vw}.toast.show{display:block}.progress{display:none;margin-top:13px}.progress.show{display:block}.progress-track{height:5px;background:#ebeee8;border-radius:4px;overflow:hidden}.progress-bar{height:100%;background:#76a85e;width:10%;transition:width .4s}.progress-text{font-size:11px;color:#68736a;margin-top:7px}.storyboard{display:none;margin-top:20px;padding:20px}.storyboard.show{display:block}.scene-row{border-top:1px solid var(--line);padding:13px 0;display:grid;grid-template-columns:34px 1fr 110px;gap:10px;align-items:start}.scene-num{color:#9aa39c;font-size:11px;padding-top:3px}.scene-row textarea{height:68px}.scene-row select{border:1px solid var(--line);padding:8px;border-radius:8px;width:100%;background:white}.scenes-top{display:flex;justify-content:space-between;margin-bottom:10px}.hidden{display:none!important}.characters-section{display:none;margin-top:20px;padding:22px}body.characters-active .characters-section{display:block}body.characters-active .content>.heading,body.characters-active .content>.workspace,body.characters-active .content>#storyboard{display:none!important}.tab-jump{border:1px solid var(--line);background:#fff;color:var(--green);border-radius:9px;padding:8px 11px;font-size:11px;font-weight:700}.settings-section{display:none;margin-top:20px;padding:26px}.settings-form{display:grid;grid-template-columns:1fr 1fr;gap:14px;max-width:720px;margin-top:24px}.settings-form label{font-size:12px;font-weight:700;display:grid;gap:7px}.settings-form input,.settings-form select{height:43px;border:1px solid var(--line);border-radius:9px;padding:10px;background:#fff}.settings-form .wide{grid-column:1/-1}.settings-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.settings-actions .btn-primary{flex:0 0 auto}.settings-actions .danger{color:#a6483a}.settings-status{margin-top:15px;color:#4c6850;font-weight:600;font-size:12px}.settings-note{margin-top:19px;padding:12px 14px;border-radius:9px;background:#f4f5f0;color:#758076;font-size:11px;max-width:720px}body.characters-active .content>.heading,body.characters-active .content>.workspace,body.characters-active .content>#storyboard,body.characters-active .content>#aiSettings{display:none!important}body.settings-active .content>.heading,body.settings-active .content>.workspace,body.settings-active .content>#storyboard,body.settings-active .content>#characters{display:none!important}body.settings-active .content>#aiSettings{display:block}.nav [data-tab].active{background:#eaf1e8;color:var(--green);font-weight:700}.character-form{display:grid;grid-template-columns:1fr 1fr;gap:12px}.character-form label{font-size:11px;font-weight:700;color:#566158;display:grid;gap:6px}.character-form input,.character-form select{width:100%;height:40px;border:1px solid #e5e8e1;border-radius:9px;background:#fdfdfb;padding:9px;outline:none}.character-form input[type=color]{padding:4px}.character-form .wide{grid-column:1/-1}.character-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(130px,1fr));gap:11px;margin-top:18px}.character-card{border:1px solid var(--line);border-radius:11px;overflow:hidden;background:#fbfcf9}.character-card img{width:100%;height:115px;object-fit:contain;background:#eef2ea}.character-card div{padding:9px}.character-card b{font-size:12px}.character-card small{display:block;color:var(--muted);font-size:10px;margin-top:3px}.character-actions{display:flex;gap:6px;margin-top:9px}.character-actions button{flex:1;padding:6px 5px;border:1px solid var(--line);border-radius:7px;background:#fff;color:#59645c;font-size:10px}.character-actions button:hover{border-color:#91aa8d;color:var(--green)}.character-actions .delete{color:#ad5142}.char-create{display:flex;justify-content:space-between;align-items:center;margin:15px 0}.char-create h3{font:700 15px Manrope;margin:0}.char-empty{grid-column:1/-1;text-align:center;color:var(--muted);padding:18px;font-size:12px}@media(max-width:950px){.layout{grid-template-columns:70px 1fr}.side{padding:20px 10px}.brand{padding:0 7px}.brand>div:last-child,.nav-label,.nav button span:not(.ico),.project{display:none}.nav button{justify-content:center;padding:12px}.workspace{grid-template-columns:1fr}.right{grid-template-columns:1fr 1fr}.tip{grid-column:1/-1}}@media(max-width:650px){.layout{display:block}.side{display:none}.topbar{height:57px;padding:0 18px}.content{padding:24px 16px}.heading{display:block}.stepper{margin-top:17px}.workspace{grid-template-columns:1fr}.right{grid-template-columns:1fr}.tip{grid-column:auto}.input-card{padding:17px}textarea{height:220px}}

:root{--ink:#e8f0eb;--muted:#9aa9a1;--paper:#0a100f;--white:#111a18;--line:#26342f;--green:#9ae2bc;--lime:#c8e5a2;--orange:#f09a75;--soft:#14231d;--shadow:0 16px 44px #00000035}
body{background:radial-gradient(ellipse at 76% 0%,#14241e 0,#0a100f 48%);color:var(--ink)}
.side,.topbar{background:#0d1513;border-color:#24312c}
.brand{color:#eaf4ed}.brandmark{background:linear-gradient(145deg,#51bd87,#267451);box-shadow:0 7px 20px #44b77a30}
.nav-label,.crumb,.hint,.project p{color:#8e9e95}.crumb b{color:#e6efe9}.nav button{color:#aebbb4}.nav button:hover{background:#17231e;color:#e4f0e8}.nav button.active{background:#183126;color:#a5e9c3}
.project{background:linear-gradient(145deg,#17251f,#121b17);border:1px solid #2a3c32}.project b{color:#cdebd8}
.card{background:#111a18;border-color:#26342f;box-shadow:0 15px 42px #00000022}
.heading h1,.card-title h2,.preview-head b,.details h3,.scenes-top h2{color:#ecf4ef}.heading p{color:#9aa9a1}.eyebrow{color:#8dd7ae}
.title-input,textarea,.character-form input,.character-form select,.settings-form input,.settings-form select,.scene-row select{background:#0b1311;color:#e9f2ec;border-color:#2a3933}
.title-input:focus,textarea:focus,.settings-form input:focus,.settings-form select:focus{border-color:#4b9b70;box-shadow:0 0 0 3px #4aa97920}
input::placeholder,textarea::placeholder{color:#73837a}.toolbar,.preview-foot small{color:#8d9d94}.examples button{background:#111a18;border-color:#2a3933;color:#b9c8bf}.examples button:hover{background:#182720;border-color:#4b775d;color:#b3ebcb}
.btn-primary{background:#287853;color:#f5fff8;box-shadow:0 5px 16px #17583b55}.btn-primary:hover{background:#328a60}.btn-secondary,.tab-jump{background:#18231e;color:#d5e5db;border:1px solid #304139}.btn-secondary:hover,.tab-jump:hover{background:#202e27;border-color:#4b6c58}
.stepper{color:#829188}.step i{border-color:#34433b;color:#a9b7ae}.step.on{color:#a2e5bd}.step.on i{background:#1d6945;border-color:#57b681;color:#f3fff6}
.preview-stage{background:#18251f}.stage-tag{background:#101815e8;color:#d7e5dc}.duration,.voice{color:#b6c4bb}.voice{border-color:#293832}.voice b{color:#dce9e0}.chip{background:#19251f;color:#aab9b0}.chip strong{color:#d8e9df}.tip{background:#14231c;color:#b8c8be}.tip strong{color:#9ee2b9}
.scene-row{border-color:#293832}.scene-num{color:#87968d}.scene-row textarea{background:#0d1513;color:#e6efe9}.storyboard,.characters-section,.settings-section{background:#111a18}.character-card{background:#0d1513;border-color:#2a3933}.character-card img{background:#17221d}.character-card b{color:#e5efe8}.character-card small{color:#92a198}.character-actions button{background:#131d19;border-color:#304139;color:#c2d0c7}.character-actions button:hover{background:#1d2c24;border-color:#4b775d;color:#b3ebcb}.character-actions .delete{color:#f09a91}.char-empty{color:#9aa9a1}
.settings-note{background:#17231e;color:#aab9b0}.settings-status{color:#a4e1b9}.settings-actions .danger{color:#f09a91}.settings-form label,.character-form label,.label{color:#cad8cf}
.status{color:#a5b4ab}.dot{background:#65c28b;box-shadow:0 0 10px #65c28b80}
@media(max-width:650px){.topbar{background:#0d1513}.content{padding-top:22px}}

:root{--ink:#eee5dd;--muted:#b6a59e;--paper:#100c12;--white:#1b141d;--line:#382731;--green:#dfb078;--lime:#e4c395;--orange:#df8b76;--soft:#241820;--shadow:0 22px 70px #05030799}
body{background:radial-gradient(ellipse at 69% 0%,#39232f 0,#19121b 38%,#0d0b11 78%);color:var(--ink)}
body:before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:linear-gradient(90deg,#100c12b3,#100c1233 47%,#100c12b8),url("https://images.unsplash.com/photo-1518709268805-4e9042af9f23?auto=format&fit=crop&w=2200&q=85") center/cover;opacity:.2;filter:saturate(.55) contrast(1.12)}
.side,.topbar{background:#120e16eF;border-color:#362631;backdrop-filter:blur(18px)}.side{box-shadow:12px 0 45px #08050a33}
.brand{color:#f3e9df}.brandmark{background:linear-gradient(145deg,#d6a46b,#82494f);box-shadow:0 7px 24px #b36d5a44}.nav-label,.crumb,.hint,.project p{color:#ae9c99}.crumb b{color:#f2e8df}.nav button{color:#c7b7b3}.nav button:hover{background:#2c1d27;color:#f4dfc4}.nav button.active{background:linear-gradient(110deg,#49303a,#2b1e29);color:#f0c991;box-shadow:inset 2px 0 #d7a46f}
.project{background:linear-gradient(145deg,#2b1d27,#19131c);border:1px solid #49303b}.project b{color:#f1d4b2}
.heading{position:relative;isolation:isolate;min-height:230px;padding:34px 38px;margin:0 0 24px;border:1px solid #76505b;border-radius:20px;overflow:hidden;align-items:center;background:linear-gradient(90deg,#160f17f5 0%,#1b1019d9 46%,#21121d55 100%),url("https://images.unsplash.com/photo-1509248961158-e54f6934749c?auto=format&fit=crop&w=1800&q=85") center 46%/cover;box-shadow:0 25px 65px #06030877}
.heading:after{content:"?";position:absolute;z-index:-1;right:7%;top:-55px;font:300 245px Georgia;color:#e9c3921c;text-shadow:0 0 50px #e5aa7555}.heading h1{color:#fff4e9;font-size:clamp(30px,4vw,46px);text-shadow:0 3px 25px #0a060acc}.heading p{color:#d2c1ba}.eyebrow{color:#e2b77f}.stepper{color:#c3aca6}.step i{border-color:#63444b;color:#e1c5ac}.step.on{color:#f1c791}.step.on i{background:#8b5448;border-color:#bd8164;color:#fff3e5}
.card{background:linear-gradient(145deg,#201720f2,#17121af5);border-color:#48313b;box-shadow:0 18px 50px #05030877;backdrop-filter:blur(12px)}.card-title h2,.preview-head b,.details h3,.scenes-top h2{color:#f5e9df}.heading h1{color:#fff4e9}.heading p{color:#d2c1ba}
.title-input,textarea,.character-form input,.character-form select,.settings-form input,.settings-form select,.scene-row select{background:#120e16;color:#f1e8e1;border-color:#493640}.title-input:focus,textarea:focus,.settings-form input:focus,.settings-form select:focus{border-color:#c58d67;box-shadow:0 0 0 3px #c18a6025}input::placeholder,textarea::placeholder{color:#8e7c7c}.toolbar,.preview-foot small{color:#b29e99}
.examples button{background:#201720;border-color:#493640;color:#d4c2b9}.examples button:hover{background:#31222b;border-color:#9d6e5c;color:#f0cca0}.btn-primary{background:linear-gradient(135deg,#b77a50,#79434b);color:#fff7ef;box-shadow:0 7px 22px #713e4355}.btn-primary:hover{background:linear-gradient(135deg,#ca8a5a,#91515a)}.btn-secondary,.tab-jump{background:#2a1e27;color:#ebdcd4;border:1px solid #58404a}.btn-secondary:hover,.tab-jump:hover{background:#382630;border-color:#a37461}
.preview-stage{background:#251922}.stage-tag{background:#171018e8;color:#f0dfd0}.duration,.voice{color:#cfbdb4}.voice{border-color:#493640}.voice b{color:#f0dfd3}.chip{background:#2a1e27;color:#d0beb7}.chip strong{color:#f1d9bb}.tip{background:#2a1d25;color:#d3beb4}.tip strong{color:#f0c793}.scene-row{border-color:#493640}.scene-num{color:#ac9892}.scene-row textarea{background:#120e16;color:#eee5dd}.storyboard,.characters-section,.settings-section{background:linear-gradient(145deg,#201720f2,#17121af5)}.character-card{background:#17121a;border-color:#493640}.character-card img{background:#241a22}.character-card b{color:#f1e7df}.character-card small{color:#b9a6a0}.character-actions button{background:#211820;border-color:#55404a;color:#dfcec6}.character-actions button:hover{background:#35242c;border-color:#a37461;color:#f0cca0}.character-actions .delete{color:#ef9a91}.char-empty{color:#c0aca5}.settings-note{background:#2a1d25;color:#cbb8af}.settings-status{color:#bbdfbe}.settings-actions .danger{color:#f09a91}.settings-form label,.character-form label,.label{color:#e0d0c8}.status{color:#cbbab0}.dot{background:#8ed19e;box-shadow:0 0 12px #8ed19e88}
@media(max-width:650px){body:before{position:absolute}.heading{min-height:205px;padding:25px 22px;background-position:62% center}.heading:after{font-size:180px;right:-5%;top:-35px}.topbar{background:#120e16}.content{padding-top:22px}}

.backgrounds-section{display:none;margin-top:20px;padding:26px}.background-form{display:grid;gap:13px;max-width:760px;margin-top:20px}.background-form label{display:grid;gap:7px;font-size:12px;font-weight:700;color:#e0d0c8}.background-form input,.background-form textarea{width:100%;border:1px solid #493640;border-radius:10px;background:#120e16;color:#f1e8e1;padding:12px;outline:none}.background-form input{height:43px}.background-form textarea{height:110px;resize:vertical}.background-list{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:24px}.background-card{overflow:hidden;border:1px solid #493640;border-radius:13px;background:#17121a}.background-card img{width:100%;aspect-ratio:16/9;object-fit:cover;display:block}.background-card>div{padding:13px}.background-card b{color:#f1e7df}.background-card p{min-height:48px;color:#b9a6a0;font-size:11px;line-height:1.5}.background-card .btn{width:100%}.background-actions{display:flex;gap:7px;margin-top:9px}.background-actions .btn{flex:1;padding:9px 8px}.background-actions .danger{color:#ef9a91}.scene-row{grid-template-columns:34px minmax(150px,1fr) 120px 155px}.scene-row select{min-width:0}@media(max-width:700px){.scene-row{grid-template-columns:28px 1fr 1fr}.scene-row textarea{grid-column:2/-1}.scene-row select{grid-row:2}.scene-row select:last-child{grid-column:3}.background-form{grid-template-columns:1fr}}
body.backgrounds-active .content>.heading,body.backgrounds-active .content>.workspace,body.backgrounds-active .content>#storyboard,body.backgrounds-active .content>#characters,body.backgrounds-active .content>#aiSettings{display:none!important}body.backgrounds-active .content>#backgrounds{display:block}
</style></head><body class="video-active"><div class="layout"><aside class="side"><div class="brand"><div class="brandmark">▶</div><div>story studio<small>TRUYỆN THÀNH PHIM</small></div></div><div><div class="nav-label">Không gian làm việc</div><nav class="nav"><button class="active" data-tab="video" onclick="switchTab('video')"><span class="ico">&#10024;</span><span>T&#7841;o video</span></button><button onclick="loadDemo()"><span class="ico">▤</span><span>Dự án mẫu</span></button><button data-tab="characters" onclick="switchTab('characters')"><span class="ico">&#9819;</span><span>Nh&#226;n v&#7853;t</span></button><button data-tab="backgrounds" onclick="switchTab('backgrounds')"><span class="ico">&#127756;</span><span>B&#7889;i c&#7843;nh</span></button><button data-tab="settings" onclick="switchTab('settings')"><span class="ico">&#9881;</span><span>C&#224;i &#273;&#7863;t AI</span></button><button onclick="switchTab('video');setTimeout(()=>document.getElementById('storyboard').scrollIntoView({behavior:'smooth'}),80)"><span class="ico">&#9775;</span><span>Storyboard</span></button><button onclick="switchTab('video');setTimeout(()=>document.getElementById('preview').scrollIntoView({behavior:'smooth'}),80)"><span class="ico">◉</span><span>Video đã xuất</span></button></nav></div><div class="project"><b>✦ &nbsp;Từ câu chuyện đến khung hình</b><p>Biến những câu chuyện của bạn thành phim hoạt hình có giọng đọc và phụ đề.</p></div></aside><main class="main"><header class="topbar"><div class="crumb">Dự án <span style="color:#c3c8c0">/</span> <b>Tạo video mới</b></div><button id="tabJump" data-tab="quick" class="tab-jump" onclick="switchTab(document.body.classList.contains('video-active')?'characters':'video')">&#9819; &nbsp;Nh&#226;n v&#7853;t</button><button class="tab-jump" data-tab="settings" onclick="switchTab('settings')">&#9881; &nbsp;C&#224;i &#273;&#7863;t AI</button><div class="status"><i class="dot"></i> Mọi thay đổi đã lưu</div></header><div class="content"><section class="heading"><div><div class="eyebrow">Story to video · studio</div><h1>Biến câu chuyện thành phim.</h1><p>Viết một câu chuyện. Để những khung hình đầu tiên xuất hiện.</p></div><div class="stepper"><span class="step on"><i>1</i> Câu chuyện</span><span class="sep">···</span><span class="step"><i>2</i> Storyboard</span><span class="sep">···</span><span class="step"><i>3</i> Video</span></div></section><section class="workspace"><div class="card input-card"><div class="card-title"><h2>Câu chuyện của bạn</h2><span class="hint">01 / 03</span></div><label class="label" for="title">Tên dự án <span>Tùy chọn</span></label><input id="title" class="title-input" placeholder="Ví dụ: Tiếng gõ cửa lúc ba giờ sáng"><label class="label" for="story">Nội dung truyện <span id="wordCount">0 từ</span></label><textarea id="story" placeholder="Ngày xửa ngày xưa, ở một ngôi làng nhỏ..."></textarea><div class="toolbar"><span>Hãy để trí tưởng tượng dẫn lối</span><div class="examples"><button onclick="loadSample()">✦ Dùng truyện mẫu</button><button onclick="document.getElementById('file').click()">↥ Tải tệp .txt</button><input id="file" class="hidden" type="file" accept=".txt,text/plain"></div></div><div class="actions"><button class="btn btn-primary" id="generate" onclick="generate()">✦ &nbsp;Phân tích & tạo storyboard <span>→</span></button></div><button class="btn btn-secondary" style="width:100%;margin-top:9px" onclick="renderDemo()">▶ &nbsp;Xem video mẫu</button><div id="progress" class="progress"><div class="progress-track"><div id="bar" class="progress-bar"></div></div><div id="progressText" class="progress-text">Đang xử lý...</div></div></div><div class="right"><div class="card preview" id="preview"><div class="preview-head"><b>Khung hình xem trước</b><span class="hint" id="previewLabel">SẴN SÀNG</span></div><div class="preview-stage" id="stage"><div class="placeholder"><div class="clapper">🎬</div><b>Chuyện của bạn bắt đầu từ đây</b><small>Video xem trước sẽ xuất hiện tại đây</small></div></div><div class="preview-foot"><small>Hoạt hình 2D · Phụ đề tiếng Việt</small><span class="duration" id="duration">--:--</span></div></div><div class="card details"><h3>Thiết lập video</h3><div class="chips"><span class="chip">🎨 &nbsp;<strong>Hoạt hình 2D</strong></span><span class="chip">📐 &nbsp;<strong>16:9 · HD</strong></span><span class="chip">💬 &nbsp;<strong>Phụ đề tự động</strong></span></div><div class="voice"><span>Giọng kể</span><b>Tiếng Việt · Tự nhiên</b></div></div><div class="tip"><strong>✦ Mẹo nhỏ</strong><br>Mỗi câu chuyện sẽ được chia thành các cảnh ngắn. Bạn có thể chỉnh lời thoại, nhân vật và bối cảnh trước khi xuất video.</div></div></section><section id="characters" class="card characters-section"><div class="eyebrow">Th&#432; vi&#7879;n t&#224;i s&#7843;n</div><div class="char-create"><h3>Nh&#226;n v&#7853;t c&#7911;a b&#7841;n</h3><button class="btn btn-secondary" onclick="refreshCharacters()">&#8635; &nbsp;L&#224;m m&#7899;i</button></div><div class="hint">T&#7841;o nh&#226;n v&#7853;t ho&#7841;t h&#236;nh 2D v&#7899;i b&#7897; bi&#7875;u c&#7843;m v&#224; mi&#7879;ng &#273;&#7897;ng t&#7921; &#273;&#7897;ng.</div><div id="characterList" class="character-list"></div><div style="border-top:1px solid var(--line);margin-top:20px;padding-top:17px"><h3 style="font:700 14px Manrope;margin:0 0 13px">&#65291; T&#7841;o nh&#226;n v&#7853;t m&#7899;i</h3><div class="character-form"><label>T&#234;n nh&#226;n v&#7853;t<input id="charName" placeholder="V&#237; d&#7909;: Mai"></label><label>Lo&#7841;i nh&#226;n v&#7853;t<select id="charKind"><option value="human">Ng&#432;&#7901;i</option><option value="dog">Ch&#243;</option><option value="cat">M&#232;o</option><option value="crocodile">C&#225; s&#7845;u</option><option value="ghost">Ma</option></select></label><label>Gi&#7899;i t&#237;nh<select id="charGender"><option value="nu">N&#7919;</option><option value="nam">Nam</option></select></label><label id="jobField">Ngh&#7873; nghi&#7879;p<select id="charJob"><option value="none">Kh&#244;ng ch&#7885;n</option><option value="doctor">B&#225;c s&#297;</option><option value="chef">&#272;&#7847;u b&#7871;p</option><option value="police">C&#244;ng an</option><option value="artist">H&#7885;a s&#297;</option><option value="office">V&#259;n ph&#242;ng</option><option value="teacher">Gi&#225;o vi&#234;n</option><option value="engineer">K&#7929; s&#432;</option><option value="farmer">N&#244;ng d&#226;n</option><option value="daoist">&#272;&#7841;o s&#297;</option></select></label><label>&#272;&#7897; tu&#7893;i<input id="charAge" type="number" min="1" max="120" value="25" placeholder="Tu&#7893;i"></label><label>M&#224;u da<input id="charSkin" type="color" value="#f1c296"></label><label>M&#224;u t&#243;c<input id="charHair" type="color" value="#1e1e23"></label><label>M&#224;u &#225;o<input id="charShirt" type="color" value="#4670aa"></label><label id="hairStyleField">Ki&#7875;u t&#243;c<select id="charStyle"><option value="long">T&#243;c d&#224;i</option><option value="bun">T&#243;c b&#250;i</option><option value="bob">T&#243;c bob</option><option value="ponytail">T&#243;c bu&#7897;c &#273;u&#244;i ng&#7921;a</option><option value="curly">T&#243;c xo&#259;n</option><option value="spiky">T&#243;c d&#7921;ng</option><option value="short">T&#243;c ng&#7855;n</option><option value="side">R&#7869; ng&#244;i</option><option value="bald_top">H&#243;i &#273;&#7881;nh &#273;&#7847;u</option></select></label><label class="wide">M&#244; t&#7843; th&#234;m<input id="charDescription" placeholder="V&#237; d&#7909;: c&#244; b&#233; vui v&#7867;, th&#237;ch kh&#225;m ph&#225;"></label></div><button id="createCharacter" class="btn btn-primary" style="margin-top:13px" onclick="createCharacter()">&#10024; &nbsp;T&#7841;o b&#7897; nh&#226;n v&#7853;t</button></div></section><section id="aiSettings" class="card settings-section"><div class="eyebrow">K&#7871;t n&#7889;i AI</div><h2 style="font:800 22px Manrope;margin:7px 0">C&#224;i &#273;&#7863;t API</h2><p class="hint">Nh&#7853;p API key &#273;&#7875; AI ph&#226;n t&#237;ch truy&#7879;n, t&#225;ch l&#7901;i nh&#226;n v&#7853;t v&#224; l&#7901;i k&#7875;.</p><div class="settings-form"><label>Nh&#224; cung c&#7845;p<select id="aiProvider" onchange="providerChanged()"><option value="muse">Meta Muse / Muse Spark</option><option value="anthropic">Anthropic</option><option value="ollama">Ollama (ch&#7841;y tr&#234;n m&#225;y)</option><option value="huggingface">Hugging Face Inference</option></select></label><label>Model<input id="aiModel" value="muse-spark-1.3"></label><label id="apiKeyField" class="wide">API key<input id="aiKey" type="password" autocomplete="new-password" placeholder="Ch&#432;a c&#243; key &#273;&#432;&#7907;c l&#432;u"></label><label id="ollamaField" class="wide hidden">&#272;&#7883;a ch&#7881; Ollama<input id="ollamaBase" value="http://localhost:11434" placeholder="http://localhost:11434"></label></div><div class="settings-actions"><button class="btn btn-primary" onclick="saveAISettings()">L&#432;u API key</button><button class="btn btn-secondary" onclick="testAISettings()">Ki&#7875;m tra k&#7871;t n&#7889;i</button><button class="btn btn-secondary danger" onclick="clearAISettings()">X&#243;a key &#273;&#227; l&#432;u</button></div><div id="aiSettingsStatus" class="settings-status" role="status">Ch&#432;a c&#7845;u h&#236;nh API.</div><div class="settings-note">API key ho&#7863;c &#273;&#7883;a ch&#7881; Ollama &#273;&#432;&#7907;c l&#432;u trong <code>local_settings.json</code> tr&#234;n m&#225;y n&#224;y. Ollama ch&#7841;y local kh&#244;ng c&#7847;n key.</div></section><section id="backgrounds" class="card backgrounds-section"><div class="eyebrow">TH&#7870; GI&#7898;I C&#7910;A C&#194;U CHUY&#7878;N</div><h2 style="font:800 22px Manrope;margin:7px 0">Th&#432; vi&#7879;n b&#7889;i c&#7843;nh</h2><p class="hint">Vi&#7871;t t&#234;n v&#224; m&#244; t&#7843; khung c&#7843;nh. B&#7843;n v&#7869; minh h&#7885;a 2D s&#7869; &#273;&#432;&#7907;c t&#7841;o v&#224; l&#432;u &#273;&#7875; ch&#7885;n trong storyboard.</p><div class="background-form"><label>T&#234;n b&#7889;i c&#7843;nh<input id="bgName" maxlength="60" placeholder="V&#237; d&#7909;: B&#7871;n &#273;&#242; l&#250;c n&#7917;a &#273;&#234;m"></label><label>M&#244; t&#7843; khung c&#7843;nh<textarea id="bgDescription" maxlength="400" placeholder="V&#237; d&#7909;: b&#7871;n c&#7847;u g&#7895; c&#361; b&#234;n d&#242;ng s&#244;ng, s&#432;&#417;ng m&#249;, &#273;&#232;n l&#7891;ng v&#224;ng, phong c&#225;ch ho&#7841;t h&#236;nh 2D"></textarea></label></div><button id="saveBackground" class="btn btn-primary" style="margin-top:13px" onclick="saveBackground()">&#10024; &nbsp;L&#432;u m&#244; t&#7843; v&#224; v&#7869; b&#7889;i c&#7843;nh</button><div id="backgroundList" class="background-list"></div></section><section id="storyboard" class="card storyboard"><div class="scenes-top"><div><div class="eyebrow">Bước 02</div><h2 style="font:700 19px Manrope;margin:5px 0">Storyboard của bạn</h2><span class="hint" id="sceneCount"></span></div><button class="btn btn-primary" style="flex:0 0 auto" onclick="renderStory()">▶ &nbsp;Tạo video</button></div><div id="sceneList"></div></section></div></main></div><div id="toast" class="toast"></div>
<script>
const $=s=>document.querySelector(s), story=$('#story');let scenes=[], characterRecords=[],backgroundRecords=[];refreshCharacters();refreshBackgrounds();$('#charKind').addEventListener('change',updateKindFields);updateKindFields();story.addEventListener('input',()=>$('#wordCount').textContent=(story.value.trim()?story.value.trim().split(/\s+/).length:0)+' từ');
function toast(t){let e=$('#toast');e.textContent=t;e.classList.add('show');setTimeout(()=>e.classList.remove('show'),3300)}
function switchTab(name){document.body.classList.toggle('video-active',name==='video');document.body.classList.toggle('characters-active',name==='characters');document.body.classList.toggle('settings-active',name==='settings');document.body.classList.toggle('backgrounds-active',name==='backgrounds');document.querySelectorAll('[data-tab=video],[data-tab=characters],[data-tab=settings],[data-tab=backgrounds]').forEach(b=>b.classList.toggle('active',b.dataset.tab===name));$('#tabJump').innerHTML=name==='video'?'&#9819; &nbsp;Nh&#226;n v&#7853;t':'&#9654; &nbsp;T&#7841;o video';document.querySelector('.crumb b').innerHTML=name==='characters'?'Nh&#226;n v&#7853;t':name==='settings'?'C&#224;i &#273;&#7863;t AI':name==='backgrounds'?'B&#7889;i c&#7843;nh':'T&#7841;o video m&#7899;i';if(name==='settings')loadAISettings();if(name==='backgrounds')refreshBackgrounds()}
function providerChanged(){let p=$('#aiProvider').value;$('#aiModel').value=p==='muse'?'muse-spark-1.3':p==='ollama'?'qwen2.5:7b':p==='huggingface'?'Qwen/Qwen2.5-7B-Instruct-1M:fastest':'claude-sonnet-5-5';$('#apiKeyField').classList.toggle('hidden',p==='ollama');$('#ollamaField').classList.toggle('hidden',p!=='ollama');$('#aiKey').placeholder=p==='ollama'?'Ollama khong can API key':'Nhap token '+(p==='muse'?'Meta Muse':p==='huggingface'?'Hugging Face':'Anthropic')}
async function loadAISettings(){try{let r=await fetch('/api/settings'),d=await r.json();$('#aiProvider').value=d.provider;$('#ollamaBase').value=d.base_url||'http://localhost:11434';providerChanged();$('#aiModel').value=d.model;if(d.configured){$('#aiKey').value='';$('#aiKey').placeholder=d.provider==='ollama'?'Ollama khong can API key':'Da luu key - nhap key moi neu muon thay';$('#aiSettingsStatus').textContent=d.provider==='ollama'?'Da luu may chu Ollama cuc bo.':'Da luu API key cho '+(d.provider==='muse'?'Meta Muse':'Anthropic')+'.'}else{$('#aiKey').placeholder='Dan API key vao day';$('#aiSettingsStatus').textContent='Chua cau hinh API key.'}}catch(e){$('#aiSettingsStatus').textContent='Khong doc duoc cai dat.'}}
async function saveAISettings(){try{let r=await fetch('/api/settings',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({provider:$('#aiProvider').value,model:$('#aiModel').value,api_key:$('#aiKey').value,base_url:$('#ollamaBase').value})}),d=await r.json();if(!r.ok)throw Error(d.error);$('#aiKey').value='';await loadAISettings();$('#aiSettingsStatus').textContent=d.provider==='ollama'?'Da luu may chu Ollama cuc bo.':'Da luu. Key duoc giu rieng tren may nay.';toast('Da luu cai dat AI.');return true}catch(e){$('#aiSettingsStatus').textContent=e.message;toast(e.message);return false}}
async function testAISettings(){if(!await saveAISettings())return;try{let r=await fetch('/api/settings/test',{method:'POST'}),d=await r.json();if(!r.ok)throw Error(d.error);$('#aiSettingsStatus').textContent=d.message;toast(d.message)}catch(e){$('#aiSettingsStatus').textContent=e.message;toast(e.message)}}
async function clearAISettings(){if(!confirm('Xoa API key da luu tren may nay?'))return;try{let r=await fetch('/api/settings',{method:'DELETE'}),d=await r.json();if(!r.ok)throw Error(d.error);$('#aiKey').value='';await loadAISettings();toast('Da xoa API key da luu.')}catch(e){toast(e.message)}}
function loadDemo(){switchTab('video');loadSample();setTimeout(()=>$('#storyboard').scrollIntoView({behavior:'smooth'}),100)}
$('#file').addEventListener('change',async e=>{let f=e.target.files[0];if(f){story.value=await f.text();$('#title').value=f.name.replace(/\.txt$/i,'');story.dispatchEvent(new Event('input'))}});
async function generate(){if(story.value.trim().length<30){toast('Hãy nhập câu chuyện dài hơn một chút nhé.');story.focus();return}let b=$('#generate');b.disabled=true;b.textContent='Đang phân tích câu chuyện…';showProgress('Đang chia câu chuyện thành các cảnh…');try{let r=await fetch('/api/storyboard',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({story:story.value,title:$('#title').value})});let d=await r.json();if(!r.ok)throw Error(d.error);scenes=d.scenes;renderScenes();$('#storyboard').classList.add('show');$('#sceneCount').textContent=scenes.length+' cảnh · Bạn có thể chỉnh sửa trước khi tạo video';$('#storyboard').scrollIntoView({behavior:'smooth'});$('#progress').classList.remove('show');toast(d.message||'Storyboard đã sẵn sàng.')}catch(e){toast(e.message)}finally{b.disabled=false;b.innerHTML='✦ &nbsp;Phân tích & tạo storyboard <span>→</span>'}}
function renderScenes(){let list=$('#sceneList');list.innerHTML='';scenes.forEach((s,i)=>{let row=document.createElement('div');row.className='scene-row';let n=document.createElement('div');n.className='scene-num';n.textContent=String(i+1).padStart(2,'0');let t=document.createElement('textarea');t.value=s.text;t.setAttribute('aria-label','L?i tho?i c?nh '+(i+1));t.oninput=()=>scenes[i].text=t.value;let speaker=document.createElement('select');['narrator',...new Set([...characterRecords.map(x=>x.id),...scenes.map(x=>x.speaker).filter(x=>x!=='narrator')])].forEach(v=>{let o=document.createElement('option');o.value=v;o.textContent=v==='narrator'?'Ng??i k?':v;o.selected=v===s.speaker;speaker.append(o)});speaker.onchange=()=>scenes[i].speaker=speaker.value;let bg=document.createElement('select');backgroundRecords.forEach(v=>{let o=document.createElement('option');o.value=v.id;o.textContent=v.name;o.selected=v.id===s.background;bg.append(o)});if(!backgroundRecords.some(v=>v.id===s.background)){let o=document.createElement('option');o.value=s.background;o.textContent=s.background;o.selected=true;bg.append(o)}bg.setAttribute('aria-label','B?i c?nh c?nh '+(i+1));bg.onchange=()=>scenes[i].background=bg.value;row.append(n,t,speaker,bg);list.append(row)})}
function showProgress(text){$('#progress').classList.add('show');$('#progressText').textContent=text;$('#bar').style.width='12%'}
async function renderStory(){if(!scenes.length)return;showProgress('Đang dựng hoạt hình và tạo giọng đọc…');$('#bar').style.width='15%';try{let r=await fetch('/api/render',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenes,title:$('#title').value})}),d=await r.json();if(!r.ok)throw Error(d.error);poll(d.job)}catch(e){$('#progress').classList.remove('show');toast(e.message)}}
async function renderDemo(){showProgress('Đang tạo video mẫu…');$('#bar').style.width='15%';try{let r=await fetch('/api/render-demo',{method:'POST'}),d=await r.json();if(!r.ok)throw Error(d.error);poll(d.job)}catch(e){$('#progress').classList.remove('show');toast(e.message)}}
async function poll(id){let timer=setInterval(async()=>{try{let r=await fetch('/api/jobs/'+id),d=await r.json();$('#progressText').textContent=d.message;$('#bar').style.width=d.done?'100%':Math.min(90,20+d.progress*65)+'%';if(d.done){clearInterval(timer);$('#progress').classList.remove('show');if(d.error){toast(d.error);return}showVideo(d.url);toast('Video của bạn đã sẵn sàng!')}}catch(e){clearInterval(timer);toast('Mất kết nối khi tạo video.')}} ,1800)}
function showVideo(url){$('#stage').innerHTML='<video controls autoplay playsinline src="'+url+'?t='+Date.now()+'" style="width:100%;height:100%;object-fit:contain;background:#14221d"></video><span class="stage-tag">VIDEO ĐÃ XUẤT</span>';$('#previewLabel').textContent='HOÀN TẤT';$('#duration').textContent='MP4 · HD';let a=document.createElement('a');a.href=url;a.download='video.mp4';a.className='btn btn-secondary';a.style='margin:0 14px 14px;width:calc(100% - 28px)';a.textContent='↓  Tải video MP4';$('#preview').append(a)}
function updateKindFields(){let human=$('#charKind').value==='human';$('#jobField').classList.toggle('hidden',!human);$('#hairStyleField').classList.toggle('hidden',!human);$('#charHair').closest('label').firstChild.textContent=human?'M\u00e0u t\u00f3c':'M\u00e0u l\u00f4ng / v\u1ea3y';$('#charSkin').closest('label').firstChild.textContent=$('#charKind').value==='ghost'?'M\u00e0u ma':'M\u00e0u da';}
async function refreshCharacters(){try{let r=await fetch('/api/characters');characterRecords=await r.json();let list=$('#characterList');list.innerHTML='';if(!characterRecords.length){list.innerHTML='<div class=\"char-empty\">Ch\u01b0a c\u00f3 nh\u00e2n v\u1eadt ri\u00eang. T\u1ea1o nh\u00e2n v\u1eadt \u0111\u1ea7u ti\u00ean c\u1ee7a b\u1ea1n nh\u00e9.</div>';return}characterRecords.forEach(c=>{let card=document.createElement('article');card.className='character-card';let img=document.createElement('img');img.src=c.image+'?t='+Date.now();img.alt=c.name;let info=document.createElement('div');let b=document.createElement('b');b.textContent=c.name;let small=document.createElement('small');small.textContent=(c.kind?c.kind+' \u00b7 ':'')+c.gender+(c.age?' \u00b7 '+c.age+' tu\u1ed5i':'')+(c.job?' \u00b7 '+c.job:'')+(c.description?' \u00b7 '+c.description:'');let actions=document.createElement('div');actions.className='character-actions';let remake=document.createElement('button');remake.textContent='\u21bb T\u1ea1o bi\u1ebfn th\u1ec3';remake.onclick=()=>regenerateCharacter(c.id);let del=document.createElement('button');del.className='delete';del.textContent='X\u00f3a';del.onclick=()=>deleteCharacter(c.id,c.name);actions.append(remake,del);info.append(b,small,actions);card.append(img,info);list.append(card)});if(scenes.length)renderScenes()}catch(e){toast('Kh\u00f4ng t\u1ea3i \u0111\u01b0\u1ee3c th\u01b0 vi\u1ec7n nh\u00e2n v\u1eadt.')}}
async function regenerateCharacter(id){if(!confirm('T\u1ea1o m\u1ed9t ngo\u1ea1i h\u00ecnh m\u1edbi cho nh\u00e2n v\u1eadt n\u00e0y?'))return;try{let r=await fetch('/api/characters/'+encodeURIComponent(id)+'/regenerate',{method:'POST'}),d=await r.json();if(!r.ok)throw Error(d.error);await refreshCharacters();toast(d.message)}catch(e){toast(e.message)}}
async function deleteCharacter(id,name){if(!confirm('X\u00f3a nh\u00e2n v\u1eadt '+name+' v\u00e0 to\u00e0n b\u1ed9 h\u00ecnh bi\u1ec3u c\u1ea3m c\u1ee7a nh\u00e2n v\u1eadt n\u00e0y?'))return;try{let r=await fetch('/api/characters/'+encodeURIComponent(id),{method:'DELETE'}),d=await r.json();if(!r.ok)throw Error(d.error);await refreshCharacters();toast('Đ\u00e3 x\u00f3a nh\u00e2n v\u1eadt '+name)}catch(e){toast(e.message)}}
async function createCharacter(){let name=$('#charName').value.trim();if(!name){toast('Nhập tên nhân vật trước nhé.');return}let b=$('#createCharacter');b.disabled=true;b.textContent='Đang vẽ bộ biểu cảm…';try{let r=await fetch('/api/characters',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,gender:$('#charGender').value,age:$('#charAge').value,kind:$('#charKind').value,job:$('#charJob').value,skin:$('#charSkin').value,hair:$('#charHair').value,shirt:$('#charShirt').value,style:$('#charStyle').value,description:$('#charDescription').value})});let d=await r.json();if(!r.ok)throw Error(d.error);await refreshCharacters();$('#charName').value='';toast('Đã tạo nhân vật '+d.name+' với 14 biểu cảm.')}catch(e){toast(e.message)}finally{b.disabled=false;b.innerHTML='✦ &nbsp;Tạo bộ nhân vật'}}
async function refreshBackgrounds(){try{let r=await fetch('/api/backgrounds');backgroundRecords=await r.json();let list=$('#backgroundList');if(!list)return;list.innerHTML='';if(!backgroundRecords.length){list.innerHTML='<div class="char-empty">Ch?a c? b?i c?nh t? t?o. H?y t?o b?i c?nh ??u ti?n.</div>';return}backgroundRecords.forEach(bg=>{let card=document.createElement('article');card.className='background-card';let img=document.createElement('img');img.src=bg.image+'?t='+Date.now();img.alt=bg.name;let info=document.createElement('div');let title=document.createElement('b');title.textContent=bg.name;let desc=document.createElement('p');desc.textContent=bg.description;let use=document.createElement('button');use.className='btn btn-secondary';use.textContent='D?ng trong storyboard';use.onclick=()=>{if(!scenes.length){toast('T?o storyboard tr??c r?i ch?n b?i c?nh cho t?ng c?nh nh?.');return}scenes.forEach(scene=>scene.background=bg.id);renderScenes();switchTab('video');$('#storyboard').scrollIntoView({behavior:'smooth'});toast('?? ??t '+bg.name+' cho c?c c?nh.')};let actions=document.createElement('div');actions.className='background-actions';let variant=document.createElement('button');variant.className='btn btn-secondary';variant.textContent='? T?o bi?n th?';variant.onclick=()=>regenerateBackground(bg);let del=document.createElement('button');del.className='btn btn-secondary danger';del.textContent='X?a';del.onclick=()=>deleteBackground(bg);actions.append(variant,del);info.append(title,desc,use,actions);card.append(img,info);list.append(card)});if(scenes.length)renderScenes()}catch(e){toast('Kh?ng t?i ???c th? vi?n b?i c?nh.')}}
async function regenerateBackground(bg){if(!confirm('V? m?t bi?n th? m?i cho ?'+bg.name+'?? ?nh hi?n t?i s? ???c thay th?.'))return;try{let r=await fetch('/api/backgrounds/'+encodeURIComponent(bg.id)+'/variant',{method:'POST'}),d=await r.json();if(!r.ok)throw Error(d.error);await refreshBackgrounds();toast('?? v? bi?n th? m?i cho '+bg.name)}catch(e){toast(e.message)}}
async function deleteBackground(bg){if(!confirm('X?a b?i c?nh ?'+bg.name+'? c?ng ?nh ?? v??'))return;try{let r=await fetch('/api/backgrounds/'+encodeURIComponent(bg.id),{method:'DELETE'}),d=await r.json();if(!r.ok)throw Error(d.error);await refreshBackgrounds();let fallback=backgroundRecords[0]?.id||'default';scenes.forEach(scene=>{if(scene.background===bg.id)scene.background=fallback});if(scenes.length)renderScenes();toast('?? x?a b?i c?nh '+bg.name)}catch(e){toast(e.message)}}
async function saveBackground(){let name=$('#bgName').value.trim(),description=$('#bgDescription').value.trim();if(!name||!description){toast('Nh?p t?n v? m? t? b?i c?nh tr??c nh?.');return}let b=$('#saveBackground');b.disabled=true;b.textContent='?ang v? b?i c?nh?';try{let r=await fetch('/api/backgrounds',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name,description})}),d=await r.json();if(!r.ok)throw Error(d.error);await refreshBackgrounds();$('#bgName').value='';$('#bgDescription').value='';toast('?? l?u v? v? b?i c?nh '+name)}catch(e){toast(e.message)}finally{b.disabled=false;b.innerHTML='&#10024; &nbsp;L?u m? t? v? v? b?i c?nh'}}
async function loadSample(){try{let r=await fetch('/api/sample'),d=await r.json();story.value=d.story;$('#title').value=d.title;story.dispatchEvent(new Event('input'));toast('Đã tải câu chuyện mẫu.')}catch(e){toast('Không tải được truyện mẫu.')}}
</script></body></html>'''


@app.get("/")
def index():
    return render_template_string(PAGE)


@app.get("/api/sample")
def sample():
    return jsonify(title="Tiếng gõ cửa lúc ba giờ sáng", story=(ROOT / "truyen_mau.txt").read_text(encoding="utf-8"))


@app.get("/api/settings")
def get_settings():
    settings = active_ai_settings()
    configured = bool(settings["api_key"]) or (settings["provider"] == "ollama" and bool(settings.get("base_url")))
    return jsonify(provider=settings["provider"], model=settings["model"], base_url=settings.get("base_url", ""), configured=configured)


@app.post("/api/settings")
def save_settings():
    data = request.get_json(force=True)
    provider = str(data.get("provider", "muse"))
    if provider not in ("muse", "anthropic", "ollama", "huggingface"):
        return jsonify(error="Nhà cung cấp API không hợp lệ."), 400
    default_model = {"muse": "muse-spark-1.3", "anthropic": "claude-sonnet-5-5", "ollama": "qwen2.5:7b",
                     "huggingface": "Qwen/Qwen2.5-7B-Instruct-1M:fastest"}[provider]
    model = str(data.get("model", default_model)).strip()
    if not model or len(model) > 100:
        return jsonify(error="Tên model không hợp lệ."), 400
    local = read_local_settings()
    if provider == "ollama":
        base_url = str(data.get("base_url", "http://localhost:11434")).strip().rstrip("/")
        if not re.fullmatch(r"https?://[A-Za-z0-9._:\[\]-]+(?::\d+)?", base_url):
            return jsonify(error="Địa chỉ Ollama phải là URL http(s) hợp lệ, ví dụ http://localhost:11434."), 400
        saved = {"provider": provider, "model": model, "base_url": base_url}
        with SETTINGS_LOCK:
            temp_path = SETTINGS_PATH.with_suffix(".tmp")
            temp_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(SETTINGS_PATH)
        return jsonify(ok=True, provider=provider, model=model, base_url=base_url, configured=True)
    api_key = str(data.get("api_key", "")).strip()
    if not api_key and local.get("provider") == provider:
        api_key = local.get("api_key", "")
    if not api_key:
        env_name = {"muse": "MODEL_API_KEY", "anthropic": "ANTHROPIC_API_KEY", "huggingface": "HF_TOKEN"}.get(provider, "")
        api_key = os.environ.get(env_name, "") if env_name else ""
        if provider == "muse":
            api_key = api_key or os.environ.get("MUSE_API_KEY", "")
        elif provider == "huggingface":
            api_key = api_key or os.environ.get("HUGGINGFACEHUB_API_TOKEN", "")
    if not api_key:
        return jsonify(error="Nhập API key trước khi lưu."), 400
    if len(api_key) > 500:
        return jsonify(error="API key có độ dài không hợp lệ."), 400
    saved = {"provider": provider, "api_key": api_key, "model": model}
    with SETTINGS_LOCK:
        temp_path = SETTINGS_PATH.with_suffix(".tmp")
        temp_path.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(SETTINGS_PATH)
    return jsonify(ok=True, provider=provider, model=model, configured=True)


@app.post("/api/settings/test")
def test_settings():
    settings = active_ai_settings()
    if settings["provider"] != "ollama" and not settings["api_key"]:
        return jsonify(error="Chưa lưu API key."), 400
    try:
        if settings["provider"] == "ollama":
            req = urllib.request.Request(settings["base_url"].rstrip("/") + "/api/chat", data=json.dumps({
                "model": settings["model"], "messages": [{"role": "user", "content": "Reply with only OK."}],
                "stream": False, "options": {"num_predict": 24},
            }).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(req, timeout=45) as response:
                response.read()
            return jsonify(ok=True, message="Kết nối Ollama thành công.")
        if settings["provider"] == "huggingface":
            import storyboard as storylib
            storylib.configure_client("huggingface", settings["api_key"], settings["model"])
            storylib.ask_json("Return only a JSON object.", "Return {\"ok\": true}.", max_tokens=32)
            return jsonify(ok=True, message="Kết nối Hugging Face thành công.")
        import storyboard as storylib
        client = storylib.configure_client(settings["provider"], settings["api_key"], settings["model"], settings.get("base_url"))
        client.messages.create(model=settings["model"], max_tokens=24,
                               messages=[{"role": "user", "content": "Reply with only OK."}])
        return jsonify(ok=True, message="Kết nối API thành công.")
    except Exception as exc:
        return jsonify(error=f"Kết nối chưa thành công: {exc}"), 400


@app.delete("/api/settings")
def clear_settings():
    with SETTINGS_LOCK:
        SETTINGS_PATH.unlink(missing_ok=True)
    return jsonify(ok=True)


@app.get("/api/backgrounds")
def list_backgrounds():
    path = ROOT / "assets" / "backgrounds.json"
    try:
        records = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except json.JSONDecodeError:
        records = []
    return jsonify([dict(item, image=f"/api/backgrounds/{item['id']}/image") for item in records if (ROOT / "assets" / "backgrounds" / f"{item.get('id','')}.png").is_file()])


@app.get("/api/backgrounds/<bid>/image")
def background_image(bid):
    if not re.fullmatch(r"[a-z0-9_]+", bid):
        abort(404)
    path = ROOT / "assets" / "backgrounds" / f"{bid}.png"
    if not path.is_file():
        abort(404)
    return send_file(path, mimetype="image/png", conditional=True)


@app.post("/api/backgrounds/<bid>/variant")
def regenerate_background(bid):
    if not re.fullmatch(r"[a-z0-9_]+", bid):
        abort(404)
    metadata_path = ROOT / "assets" / "backgrounds.json"
    try:
        records = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else []
    except json.JSONDecodeError:
        records = []
    item = next((entry for entry in records if entry.get("id") == bid), None)
    if item is None:
        return jsonify(error="Kh?ng t?m th?y b?i c?nh."), 404
    try:
        import assetgen
        assetgen.generate_background(bid, ROOT / "assets" / "backgrounds" / f"{bid}.png",
                                     item.get("description", ""), variant_seed=secrets.token_hex(8))
        return jsonify(ok=True, image=f"/api/backgrounds/{bid}/image")
    except Exception as exc:
        return jsonify(error=f"Kh?ng v? ???c bi?n th?: {exc}"), 500


@app.delete("/api/backgrounds/<bid>")
def delete_background(bid):
    if not re.fullmatch(r"[a-z0-9_]+", bid):
        abort(404)
    metadata_path = ROOT / "assets" / "backgrounds.json"
    try:
        records = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else []
    except json.JSONDecodeError:
        records = []
    remaining = [entry for entry in records if entry.get("id") != bid]
    if len(remaining) == len(records):
        return jsonify(error="Kh?ng t?m th?y b?i c?nh."), 404
    try:
        metadata_path.write_text(json.dumps(remaining, ensure_ascii=False, indent=2), encoding="utf-8")
        (ROOT / "assets" / "backgrounds" / f"{bid}.png").unlink(missing_ok=True)
        return jsonify(ok=True)
    except OSError as exc:
        return jsonify(error=f"Kh?ng x?a ???c b?i c?nh: {exc}"), 500


@app.post("/api/backgrounds")
def create_background():
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    description = str(data.get("description", "")).strip()
    if not name or len(name) > 60 or not description or len(description) > 400:
        return jsonify(error="Nh?p t?n (t?i ?a 60 k? t?) v? m? t? (t?i ?a 400 k? t?) cho b?i c?nh."), 400
    ascii_name = "".join(ch for ch in unicodedata.normalize("NFKD", name.lower()) if not unicodedata.combining(ch))
    bid = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_") or f"boi_canh_{uuid.uuid4().hex[:6]}"
    metadata_path = ROOT / "assets" / "backgrounds.json"
    try:
        records = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.exists() else []
    except json.JSONDecodeError:
        records = []
    if not any(item.get("id") == bid for item in records) and (ROOT / "assets" / "backgrounds" / f"{bid}.png").exists():
        bid = f"{bid}_{uuid.uuid4().hex[:4]}"
    item = {"id": bid, "name": name, "description": description}
    records = [old for old in records if old.get("id") != bid]
    records.append(item)
    try:
        import assetgen
        assetgen.generate_background(bid, ROOT / "assets" / "backgrounds" / f"{bid}.png", description)
        metadata_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(**item, image=f"/api/backgrounds/{bid}/image")
    except Exception as exc:
        return jsonify(error=f"Kh?ng v? ???c b?i c?nh: {exc}"), 500


@app.get("/api/characters")
def list_characters():
    return jsonify(character_records())


@app.get("/api/characters/<cid>/image")
def character_image(cid):
    if not re.fullmatch(r"[a-z0-9_]+", cid):
        abort(404)
    path = ROOT / "assets" / "characters" / cid / "neutral.png"
    if not path.exists():
        abort(404)
    return send_file(path, mimetype="image/png", conditional=True)


@app.post("/api/characters/<cid>/regenerate")
def regenerate_character(cid):
    if not re.fullmatch(r"[a-z0-9_]+", cid):
        abort(404)
    cast_path = ROOT / "assets" / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else {}
    if cid not in cast:
        return jsonify(error="Không tìm thấy nhân vật."), 404
    try:
        import assetgen
        spec = cast[cid]
        gender = spec.get("gender", "nam")
        # A new seed changes the generator's palette and hairstyle while preserving identity.
        job = spec.get("job", "none")
        kind = spec.get("kind", "human")
        varied = assetgen.make_spec(cid + secrets.token_hex(8), gender)
        for key in ("skin", "hair", "shirt", "pants"):
            varied[key] = "#%02x%02x%02x" % tuple(varied[key])
        spec.update(varied)
        spec["name"] = cast[cid].get("name", cid)
        spec["gender"] = gender
        spec["age"] = cast[cid].get("age", 25)
        spec["description"] = cast[cid].get("description", "")
        spec["job"] = job
        spec["kind"] = kind
        assetgen.generate_character_set(cid, gender, ROOT / "assets" / "characters" / cid, spec)
        cast_path.write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(ok=True, image=f"/api/characters/{cid}/image", message="Đã tạo một biến thể ngoại hình mới.")
    except Exception as exc:
        return jsonify(error=f"Không tạo được biến thể: {exc}"), 500


@app.delete("/api/characters/<cid>")
def delete_character(cid):
    if not re.fullmatch(r"[a-z0-9_]+", cid):
        abort(404)
    cast_path = ROOT / "assets" / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else {}
    if cid not in cast:
        return jsonify(error="Không tìm thấy nhân vật."), 404
    folder = (ROOT / "assets" / "characters" / cid).resolve()
    expected_parent = (ROOT / "assets" / "characters").resolve()
    if folder.parent != expected_parent:
        abort(400)
    if folder.exists():
        try:
            shutil.rmtree(folder)
        except PermissionError:
            return jsonify(error="Một hình của nhân vật đang được mở. Đóng/xóa ảnh trong thư viện rồi thử lại."), 409
    del cast[cid]
    cast_path.write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify(ok=True)


@app.post("/api/characters")
def create_character():
    data = request.get_json(force=True)
    name = str(data.get("name", "")).strip()
    if not name or len(name) > 50:
        return jsonify(error="Tên nhân vật cần có từ 1 đến 50 ký tự."), 400
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
    cid = re.sub(r"[^a-z0-9]+", "_", ascii_name).strip("_") or f"nhan_vat_{uuid.uuid4().hex[:6]}"
    cast_path = ROOT / "assets" / "cast.json"
    cast = json.loads(cast_path.read_text(encoding="utf-8")) if cast_path.exists() else {}
    if cid in cast:
        return jsonify(error="Tên nhân vật này đã tồn tại. Hãy chọn tên khác."), 409
    gender = data.get("gender", "nu")
    if gender == "nu":
        gender = "nữ"
    if gender not in ("nam", "nữ"):
        return jsonify(error="Giới tính không hợp lệ."), 400
    try:
        age = int(data.get("age", 25))
    except (TypeError, ValueError):
        return jsonify(error="Độ tuổi phải là số từ 1 đến 120."), 400
    if not 1 <= age <= 120:
        return jsonify(error="Độ tuổi phải từ 1 đến 120."), 400
    spec = {"name": name, "gender": gender, "age": age,
            "skin": data.get("skin", "#f1c296"), "hair": data.get("hair", "#1e1e23"),
            "shirt": data.get("shirt", "#4670aa"), "style": data.get("style", "long"),
            "description": str(data.get("description", ""))[:200],
            "job": str(data.get("job", "none"))}
    for key in ("skin", "hair", "shirt"):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", spec[key]):
            return jsonify(error="Mã màu không hợp lệ."), 400
    if spec["style"] not in ("long", "bun", "bob", "ponytail", "curly", "spiky", "short", "side", "bald_top"):
        return jsonify(error="Kiểu tóc không hợp lệ."), 400
    kind = str(data.get("kind", "human"))
    if kind not in ("human", "dog", "cat", "crocodile", "ghost"):
        return jsonify(error="Loại nhân vật không hợp lệ."), 400
    spec["kind"] = kind
    if kind != "human":
        spec["job"] = "none"
    if spec["job"] not in ("none", "doctor", "chef", "police", "artist", "office", "teacher", "engineer", "farmer", "daoist"):
        return jsonify(error="Nghề nghiệp không hợp lệ."), 400
    try:
        import assetgen
        folder = ROOT / "assets" / "characters" / cid
        assetgen.generate_character_set(cid, gender, folder, spec)
        cast[cid] = spec
        cast_path.write_text(json.dumps(cast, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(id=cid, name=name, image=f"/api/characters/{cid}/image", emotions=14)
    except Exception as exc:
        return jsonify(error=f"Không tạo được nhân vật: {exc}"), 500


@app.post("/api/storyboard")
def storyboard():
    data = request.get_json(force=True)
    story = str(data.get("story", "")).strip()
    if len(story) < 30:
        return jsonify(error="Câu chuyện quá ngắn. Hãy nhập ít nhất 30 ký tự."), 400
    try:
        ai = active_ai_settings()
        if ai["provider"] != "ollama" and not ai["api_key"]:
            # Bản fallback chia theo câu, không viết lại nội dung; cho phép dùng app
            # offline với storyboard thủ công và khả năng render vốn có.
            import json as _json
            bible = _json.loads((ROOT / "storyboard_truyen_mau.json").read_text(encoding="utf-8")).get("bible", {})
            chars = bible.get("characters", [])
            bgs = bible.get("backgrounds", [])
            bg = bgs[0].get("id", "default") if bgs else "default"
            sentences = [s.strip() for s in re.split(r"(?<=[.!?…])\s+|\n+", story) if s.strip()]
            scenes = []
            for sentence in sentences:
                chunks = re.split(r"(?<=[,;:])\s+", sentence)
                current = ""
                for chunk in chunks:
                    if current and len(current.split()) + len(chunk.split()) > 25:
                        scenes.append({"speaker": "narrator", "text": current.strip(), "emotion": "neutral", "background": bg, "characters": []})
                        current = ""
                    current = (current + " " + chunk).strip()
                if current:
                    scenes.append({"speaker": "narrator", "text": current, "emotion": "neutral", "background": bg, "characters": []})
            if not scenes:
                return jsonify(error="Không tìm thấy câu nào trong truyện."), 400
            sid = str(uuid.uuid4())[:8]
            path = ROOT / "build" / f"storyboard_{sid}.json"
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps({"bible": {"characters": chars, "backgrounds": bgs}, "scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
            return jsonify(scenes=scenes, storyboard=str(path), message=f"Đã chia thành {len(scenes)} cảnh cơ bản. Bạn có thể sửa lời thoại rồi tạo video.")
        import storyboard as storylib
        storylib.configure_client(ai["provider"], ai["api_key"], ai["model"], ai.get("base_url"))
        bible = storylib.ask_json(storylib.BIBLE_SYS, story[:60000], max_tokens=3000)
        scenes = []
        for chunk in storylib.chunk_story(story):
            context = json.dumps(scenes[-2:], ensure_ascii=False)
            prompt = (f"STORY BIBLE:\n{json.dumps(bible, ensure_ascii=False)}\n\n"
                      f"HAI CẢNH CUỐI CỦA ĐOẠN TRƯỚC:\n{context}\n\nĐOẠN TRUYỆN CẦN CHIA:\n{chunk}")
            part = storylib.ask_json(storylib.SCENE_SYS, prompt)
            ids_c = [c["id"] for c in bible.get("characters", [])]
            ids_b = [b["id"] for b in bible.get("backgrounds", [])]
            for scene in part:
                if scene["speaker"] != "narrator" and scene["speaker"] not in ids_c:
                    scene["speaker"] = "narrator"
                scene["characters"] = [c for c in scene.get("characters", []) if c in ids_c]
                if ids_b and scene["background"] not in ids_b:
                    scene["background"] = ids_b[0]
                if scene.get("emotion") not in storylib.EMOTIONS.split("|"):
                    scene["emotion"] = "neutral"
            scenes.extend(part)
        sid = str(uuid.uuid4())[:8]
        path = ROOT / "build" / f"storyboard_{sid}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"bible": bible, "scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
        return jsonify(scenes=scenes, storyboard=str(path), message=f"Đã tạo {len(scenes)} cảnh. Chỉnh sửa lời thoại rồi bấm Tạo video.")
    except Exception as exc:
        return jsonify(error=f"Không thể tạo storyboard: {exc}"), 500


def start_job(command, kind="render"):
    jid = str(uuid.uuid4())[:10]
    with LOCK:
        JOBS[jid] = {"done": False, "progress": 0, "message": "Đang khởi chạy…", "error": None, "kind": kind}

    def worker():
        try:
            env = os.environ.copy()
            # Windows console defaults to a legacy code page on many installs;
            # render logs contain Vietnamese story text, so force UTF-8 end-to-end.
            env["PYTHONIOENCODING"] = "utf-8"
            env["PYTHONUTF8"] = "1"
            proc = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", env=env)
            lines = []
            for line in proc.stdout:
                lines.append(line.rstrip())
                if len(lines) > 40:
                    lines.pop(0)
                with LOCK:
                    job = JOBS[jid]
                    job["message"] = line.strip()[:180] or "Đang xử lý…"
                    job["progress"] = min(0.95, job["progress"] + .018)
            code = proc.wait()
            with LOCK:
                job = JOBS[jid]
                job["done"] = True
                job["progress"] = 1
                if code == 0 and (ROOT / "video.mp4").exists():
                    job["message"] = "Video đã sẵn sàng."
                    job["url"] = "/video"
                else:
                    job["error"] = "Không tạo được video. Kiểm tra ffmpeg, edge-tts và nội dung storyboard. " + " ".join(lines[-3:])[-450:]
                    job["message"] = "Tạo video gặp lỗi."
        except FileNotFoundError as exc:
            missing = Path(str(exc.filename or "")).name or "ffmpeg"
            help_text = ("Không tìm thấy ffmpeg. Cài FFmpeg rồi thêm thư mục chứa ffmpeg.exe vào PATH, "
                         "sau đó đóng và mở lại PowerShell cùng Story Studio.") if missing.lower().startswith("ffmpeg") else f"Không tìm thấy chương trình cần chạy: {missing}."
            with LOCK:
                JOBS[jid].update(done=True, error=help_text, message="Thiếu chương trình cần thiết.")
        except Exception as exc:
            with LOCK:
                JOBS[jid].update(done=True, error=f"Không chạy được tác vụ: {exc}", message="Tạo video gặp lỗi.")

    threading.Thread(target=worker, daemon=True).start()
    return jid


@app.post("/api/render")
def render():
    data = request.get_json(force=True)
    if not shutil.which("ffmpeg"):
        return jsonify(error="Máy chưa cài FFmpeg hoặc chưa có ffmpeg.exe trong PATH. Cài FFmpeg, thêm thư mục chứa ffmpeg.exe vào PATH, rồi đóng và mở lại PowerShell và Story Studio."), 400
    scenes = data.get("scenes", [])
    if not scenes:
        return jsonify(error="Storyboard chưa có cảnh nào."), 400
    for s in scenes:
        if not all(k in s for k in ("speaker", "text", "emotion", "background")):
            return jsonify(error="Storyboard có cảnh thiếu dữ liệu."), 400
    path = ROOT / "build" / f"storyboard_ui_{uuid.uuid4().hex[:8]}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps({"scenes": scenes}, ensure_ascii=False, indent=2), encoding="utf-8")
    jid = start_job([sys.executable, str(ROOT / "make_video.py"), str(path)])
    return jsonify(job=jid)


@app.post("/api/render-demo")
def render_demo():
    if not shutil.which("ffmpeg"):
        return jsonify(error="Máy chưa cài FFmpeg hoặc chưa có ffmpeg.exe trong PATH. Cài FFmpeg, thêm thư mục chứa ffmpeg.exe vào PATH, rồi đóng và mở lại PowerShell và Story Studio."), 400
    path = ROOT / "storyboard_truyen_mau.json"
    return jsonify(job=start_job([sys.executable, str(ROOT / "make_video.py"), str(path)]))


@app.get("/api/jobs/<jid>")
def job_status(jid):
    with LOCK:
        job = JOBS.get(jid)
        if not job:
            return jsonify(error="Không tìm thấy tác vụ."), 404
        return jsonify(job)


@app.get("/video")
def video():
    path = ROOT / "video.mp4"
    if not path.exists():
        return "Chưa có video", 404
    return send_file(path, mimetype="video/mp4", conditional=True, as_attachment=request.args.get("download") == "1", download_name="video.mp4")


if __name__ == "__main__":
    print("Story Studio đang chạy tại http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
