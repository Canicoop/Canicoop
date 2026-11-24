"""Atualiza a secção "Agora" do README com os últimos commits públicos.

Uso: GITHUB_TOKEN=... python scripts/agora.py [utilizador] [README.md]
"""
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

INICIO = "<!-- agora:inicio -->"
FIM = "<!-- agora:fim -->"
MAX_MENSAGEM = 72
API = "https://api.github.com"


def tempo_relativo(quando: datetime, agora: datetime) -> str:
    dias = (agora.date() - quando.date()).days
    if dias <= 0:
        return "hoje"
    if dias == 1:
        return "ontem"
    if dias < 14:
        return f"há {dias} dias"
    if dias < 60:
        return f"há {dias // 7} semanas"
    if dias < 365:
        return f"há {dias // 30} meses"
    return "há mais de um ano"


def escapar(texto: str) -> str:
    texto = re.sub(r"([\\`*_\[\]])", r"\\\1", texto)
    return texto.replace("<", "&lt;")


def linha(c: dict, agora: datetime) -> str:
    msg = c["mensagem"].strip().splitlines()[0].strip() if c["mensagem"].strip() else "(sem mensagem)"
    if len(msg) > MAX_MENSAGEM:
        msg = msg[: MAX_MENSAGEM - 1].rstrip() + "…"
    return f"- {escapar(msg)}, em [{c['repo']}]({c['url']}), {tempo_relativo(c['data'], agora)}"


def conteudo(commits: list, agora: datetime) -> str:
    if not commits:
        return "Sem atividade pública recente."
    return "\n".join(linha(c, agora) for c in commits)


def substituir_secao(readme: str, novo: str) -> str:
    padrao = re.compile(re.escape(INICIO) + r".*?" + re.escape(FIM), re.S)
    if not padrao.search(readme):
        raise ValueError(f"README sem os marcadores {INICIO} / {FIM}")
    return padrao.sub(lambda _: f"{INICIO}\n{novo}\n{FIM}", readme, count=1)


def _get(caminho: str, token: str | None):
    req = urllib.request.Request(API + caminho, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def buscar_commits(user: str, token: str | None, n: int = 5) -> list:
    repos = _get(f"/users/{user}/repos?type=owner&sort=pushed&per_page=10", token)
    commits = []
    for repo in repos:
        if repo["fork"] or repo["private"] or repo["name"].lower() == user.lower():
            continue
        try:
            dados = _get(f"/repos/{user}/{repo['name']}/commits?per_page={n}", token)
        except urllib.error.HTTPError as e:
            if e.code == 409:  # repositório vazio
                continue
            raise
        for d in dados:
            autor = d.get("author") or {}
            if autor.get("type") == "Bot" or autor.get("login", "").endswith("[bot]"):
                continue
            commits.append({
                "repo": repo["name"],
                "mensagem": d["commit"]["message"],
                "url": d["html_url"],
                "data": datetime.fromisoformat(d["commit"]["committer"]["date"].replace("Z", "+00:00")),
            })
    commits.sort(key=lambda c: c["data"], reverse=True)
    return commits[:n]


def main() -> None:
    user = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("GITHUB_REPOSITORY_OWNER", "Canicoop")
    caminho = sys.argv[2] if len(sys.argv) > 2 else "README.md"
    agora = datetime.now(timezone.utc)
    commits = buscar_commits(user, os.environ.get("GITHUB_TOKEN"))
    with open(caminho, encoding="utf-8") as f:
        readme = f.read()
    novo = substituir_secao(readme, conteudo(commits, agora))
    if novo != readme:
        with open(caminho, "w", encoding="utf-8", newline="\n") as f:
            f.write(novo)
        print(f"README atualizado ({len(commits)} commits).")
    else:
        print("Sem alterações.")


if __name__ == "__main__":
    main()
