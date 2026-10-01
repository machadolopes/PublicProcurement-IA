"""Exporta a análise descritiva, a classificação e as figuras do artigo.

Uso (a partir da raiz do repositório)::

    python -m analysis.export_artigo
"""

from __future__ import annotations

import hashlib
import json
import platform
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from analysis.destinacao import CLASSIFIER_VERSION, load_rules, montar_corpus

ROOT = Path(__file__).resolve().parents[2]
HITS = ROOT / "data" / "raw" / "candidatas_search" / "hits.jsonl"
OUT = ROOT / "outputs" / "artigo"
FIG = OUT / "figuras"
SEED = 42

ORDEM_CLASSE = (
    "capacitacao",
    "licenca_assistente",
    "ferramenta_oficio",
    "reconhecimento_facial",
    "videomonitoramento",
    "chatbot",
    "sistema_gestao",
    "infraestrutura",
    "residual",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _quartis(values: list[float]) -> dict:
    if not values:
        return {"n": 0, "mediana": None, "q1": None, "q3": None}
    ordered = sorted(values)

    def at(q: float) -> float:
        pos = (len(ordered) - 1) * q
        lo = int(pos)
        hi = min(lo + 1, len(ordered) - 1)
        return ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo)

    return {
        "n": len(ordered),
        "mediana": round(median(ordered), 2),
        "q1": round(at(0.25), 2),
        "q3": round(at(0.75), 2),
    }


def _contagem(rows: list[dict], key: str) -> list[dict]:
    counts = Counter(row[key] or "Não informado" for row in rows)
    return [{"chave": k, "n": n} for k, n in counts.most_common()]


def _exemplos(rows: list[dict], rules_rotulo: dict[str, str]) -> dict[str, list[dict]]:
    import random

    rng = random.Random(SEED)
    por_classe: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        por_classe[row["classe_primaria"]].append(row)
    saida: dict[str, list[dict]] = {}
    for classe, grupo in por_classe.items():
        copia = list(grupo)
        rng.shuffle(copia)
        saida[classe] = [
            {
                "numero_controle_pncp": item["numero_controle_pncp"],
                "ano": item["ano"],
                "document_type": item["document_type"],
                "uf": item["uf"],
                "orgao_nome": item["orgao_nome"],
                "objeto": item["description"][:400],
                "rotulo": rules_rotulo[classe],
            }
            for item in copia[:8]
        ]
    return saida


def _associacao_classe_modalidade(
    rows: list[dict],
    rotulo: dict[str, str],
    *,
    top_modalidades: int = 5,
) -> dict:
    """Tabela classe × modalidade, % na linha e lift sob independência."""
    cont: dict[str, Counter] = {cid: Counter() for cid in ORDEM_CLASSE}
    for row in rows:
        mod = row.get("modalidade") or "Não informado"
        cont[row["classe_primaria"]][mod] += 1
    totais_mod = Counter()
    for cid in ORDEM_CLASSE:
        totais_mod.update(cont[cid])
    modalidades = [m for m, _ in totais_mod.most_common(top_modalidades)]
    outras = [m for m in totais_mod if m not in modalidades]
    if outras:
        modalidades = modalidades + ["Outras"]

    n = len(rows)
    celulas = []
    matriz_pct = []
    matriz_lift = []
    for cid in ORDEM_CLASSE:
        n_classe = sum(cont[cid].values())
        linha_pct = []
        linha_lift = []
        for mod in modalidades:
            if mod == "Outras":
                obs = sum(cont[cid][m] for m in outras)
                n_mod = sum(totais_mod[m] for m in outras)
            else:
                obs = cont[cid][mod]
                n_mod = totais_mod[mod]
            pct_linha = round(100 * obs / n_classe, 2) if n_classe else 0.0
            esperado = (n_classe * n_mod / n) if n else 0.0
            lift = round(obs / esperado, 3) if esperado > 0 else None
            residual = (
                round((obs - esperado) / (esperado**0.5), 3) if esperado > 0 else None
            )
            celulas.append(
                {
                    "classe_id": cid,
                    "classe": rotulo[cid],
                    "modalidade": mod,
                    "n": obs,
                    "pct_na_classe": pct_linha,
                    "esperado_independencia": round(esperado, 2),
                    "lift": lift,
                    "residuo_pearson": residual,
                }
            )
            linha_pct.append(pct_linha)
            linha_lift.append(lift if lift is not None else 0.0)
        matriz_pct.append(linha_pct)
        matriz_lift.append(linha_lift)

    fortes = sorted(
        [
            c
            for c in celulas
            if c["lift"] is not None and c["n"] >= 20 and c["lift"] >= 1.2
        ],
        key=lambda c: (-c["lift"], -c["n"]),
    )[:20]
    fracas = sorted(
        [
            c
            for c in celulas
            if c["lift"] is not None and c["n"] >= 20 and c["lift"] <= 0.8
        ],
        key=lambda c: (c["lift"], -c["n"]),
    )[:12]

    return {
        "nota": (
            "Lift = n observado / n esperado se classe e modalidade fossem independentes. "
            "Lift > 1: coocorrência acima do acaso; < 1: abaixo. "
            "Residual de Pearson = (obs − esp) / √esp. Modalidades raras agregadas em Outras."
        ),
        "modalidades": modalidades,
        "classes": [rotulo[cid] for cid in ORDEM_CLASSE],
        "classe_ids": list(ORDEM_CLASSE),
        "celulas": celulas,
        "matriz_pct_na_classe": matriz_pct,
        "matriz_lift": matriz_lift,
        "associacoes_acima_do_acaso": fortes,
        "associacoes_abaixo_do_acaso": fracas,
    }


def _agregar(rows: list[dict], rules) -> dict:
    n = len(rows)
    rotulo = {rule.id: rule.rotulo for rule in rules.classes}
    por_classe = Counter(row["classe_primaria"] for row in rows)
    classes = []
    for cid in ORDEM_CLASSE:
        k = por_classe.get(cid, 0)
        classes.append(
            {
                "id": cid,
                "rotulo": rotulo[cid],
                "n": k,
                "percentual": round(100 * k / n, 2) if n else 0,
            }
        )
    por_ano: dict[str, int] = defaultdict(int)
    por_classe_ano: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    multi = 0
    for row in rows:
        por_ano[row["ano"]] += 1
        por_classe_ano[row["classe_primaria"]][row["ano"]] += 1
        if len(row["classes_atingidas"]) > 1:
            multi += 1
    anos = sorted(a for a in por_ano if a)
    padroes = Counter(
        (row["classe_primaria"], row.get("padrao_primario") or "(nenhum)") for row in rows
    )
    return {
        "n": n,
        "por_ano": [{"ano": ano, "n": por_ano[ano]} for ano in anos],
        "por_esfera": _contagem(rows, "esfera_nome"),
        "por_uf": _contagem(rows, "uf"),
        "por_modalidade": _contagem(rows, "modalidade"),
        "valores": {
            "valor_global": _quartis([row["valor"] for row in rows if row["valor"]]),
            "nota": (
                "Medianas e quartis do valor global do contrato. Não some os valores: "
                "há outliers de ordem de grandeza incompatível com um contrato isolado."
            ),
        },
        "classificacao": classes,
        "por_classe_ano": {
            cid: {ano: por_classe_ano[cid].get(ano, 0) for ano in anos} for cid in ORDEM_CLASSE
        },
        "associacao_classe_modalidade": _associacao_classe_modalidade(rows, rotulo),
        "com_mais_de_uma_classe": multi,
        "padroes_que_decidiram": [
            {"classe": classe, "padrao": padrao, "n": n}
            for (classe, padrao), n in padroes.most_common()
        ],
        "exemplos": _exemplos(rows, rotulo),
    }


def _estilo():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib import font_manager

    arial = Path(r"C:\Windows\Fonts\arial.ttf")
    if arial.exists():
        font_manager.fontManager.addfont(str(arial))
        plt.rcParams["font.family"] = "Arial"
    # Figuras com cor acessível (Okabe–Ito), alto contraste no texto e eixos.
    plt.rcParams.update(
        {
            "font.size": 10,
            "axes.labelsize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "axes.linewidth": 0.8,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
            "axes.edgecolor": "black",
            "xtick.color": "black",
            "ytick.color": "black",
            "text.color": "black",
            "axes.labelcolor": "black",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "legend.frameon": False,
        }
    )
    return plt


def _salvar(fig, nome: str) -> None:
    fig.savefig(FIG / nome, dpi=300, bbox_inches="tight", facecolor="white")
    import matplotlib.pyplot as plt

    plt.close(fig)


def _pct(n: int, total: int) -> float:
    return 100.0 * n / total if total else 0.0


def _texto_barra(n: int, total: int) -> str:
    """Rótulo de barra com n e percentagem."""
    return f"{n} ({_pct(n, total):.1f}%)"


def _luminancia_relativa(hex_color: str) -> float:
    """Luminância relativa sRGB (WCAG) para escolher texto preto/branco."""
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i : i + 2], 16) / 255.0 for i in (0, 2, 4))

    def canal(c: float) -> float:
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    return 0.2126 * canal(r) + 0.7152 * canal(g) + 0.0722 * canal(b)


def _cor_texto_sobre(hex_color: str) -> str:
    # Limiar ~0.179 ≈ contraste mínimo preferível texto branco vs preto (WCAG).
    return "black" if _luminancia_relativa(hex_color) > 0.179 else "white"


# Paleta Okabe–Ito (daltonismo-segura) + cinza residual.
# Ordem alinhada a ORDEM_CLASSE.
_CORES_CLASSE = (
    "#0072B2",  # capacitacao — azul
    "#E69F00",  # licenca_assistente — laranja
    "#009E73",  # ferramenta_oficio — verde-azulado
    "#D55E00",  # reconhecimento_facial — vermelho-alaranjado
    "#CC79A7",  # videomonitoramento — rosa
    "#56B4E9",  # chatbot — azul claro
    "#F0E442",  # sistema_gestao — amarelo
    "#000000",  # infraestrutura — preto
    "#999999",  # residual — cinza
)
_COR_BARRA = "#0072B2"


def _anotar_barras_v(ax, barras, total: int, *, min_altura: float = 0.0) -> None:
    for patch in barras:
        altura = patch.get_height()
        if altura <= min_altura:
            continue
        x = patch.get_x() + patch.get_width() / 2
        ax.text(
            x,
            altura,
            _texto_barra(int(round(altura)), total),
            ha="center",
            va="bottom",
            fontsize=7,
            color="black",
            clip_on=False,
        )


def _anotar_barras_h(ax, barras, total: int, *, min_largura: float = 0.0) -> None:
    for patch in barras:
        largura = patch.get_width()
        if largura <= min_largura:
            continue
        y = patch.get_y() + patch.get_height() / 2
        ax.text(
            largura,
            y,
            f"  {_texto_barra(int(round(largura)), total)}",
            ha="left",
            va="center",
            fontsize=8,
            color="black",
            clip_on=False,
        )


def _figuras(ag: dict) -> list[dict]:
    plt = _estilo()
    n_total = int(ag["n"])
    legendas = []

    # --- Figura 1: contratos por ano ---
    anos = [row["ano"] for row in ag["por_ano"]]
    totais = [row["n"] for row in ag["por_ano"]]
    fig, ax = plt.subplots(figsize=(6.5, 3.8))
    bars = ax.bar(
        anos,
        totais,
        color=_COR_BARRA,
        edgecolor="black",
        linewidth=0.6,
        width=0.65,
    )
    _anotar_barras_v(ax, bars, n_total)
    ax.set_ylabel("Número de contratos")
    ax.set_xlabel("Ano de publicação no PNCP")
    ymax = max(totais + [0]) * 1.22
    ax.set_ylim(0, ymax if ymax else 1)
    fig.tight_layout()
    _salvar(fig, "figura1_ano.png")
    legendas.append(
        {
            "arquivo": "figura1_ano.png",
            "titulo": "Figura 1",
            "legenda": "Contratos do corpus de análise, por ano de publicação no PNCP.",
            "nota": (
                "Unidade de análise: contrato com descrição contendo o léxico de inclusão. "
                "2026 cobre janeiro a 30 de setembro. Rótulos: n e percentagem do corpus "
                f"(N = {n_total})."
            ),
        }
    )

    # --- Figura 2: esfera (decrescente; maior no topo) ---
    esferas = sorted(
        [row for row in ag["por_esfera"] if row["n"] > 0][:6],
        key=lambda row: row["n"],
    )
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    bars = ax.barh(
        [row["chave"] for row in esferas],
        [row["n"] for row in esferas],
        color=_COR_BARRA,
        edgecolor="black",
        linewidth=0.6,
    )
    _anotar_barras_h(ax, bars, n_total)
    ax.set_xlabel("Número de contratos")
    xmax = max((row["n"] for row in esferas), default=0) * 1.28
    ax.set_xlim(0, xmax if xmax else 1)
    fig.tight_layout()
    _salvar(fig, "figura2_esfera.png")
    legendas.append(
        {
            "arquivo": "figura2_esfera.png",
            "titulo": "Figura 2",
            "legenda": "Contratos do corpus de análise, por esfera do órgão.",
            "nota": (
                f"Rótulos como publicados pelo PNCP. Ordenação decrescente por n. "
                f"Percentagens sobre N = {n_total}."
            ),
        }
    )

    # --- Figura 3: UF (decrescente; maior no topo) ---
    ufs = sorted(ag["por_uf"][:12], key=lambda row: row["n"])
    fig, ax = plt.subplots(figsize=(6.5, 4.4))
    bars = ax.barh(
        [row["chave"] for row in ufs],
        [row["n"] for row in ufs],
        color=_COR_BARRA,
        edgecolor="black",
        linewidth=0.6,
    )
    _anotar_barras_h(ax, bars, n_total)
    ax.set_xlabel("Número de contratos")
    xmax = max((row["n"] for row in ufs), default=0) * 1.28
    ax.set_xlim(0, xmax if xmax else 1)
    fig.tight_layout()
    _salvar(fig, "figura3_uf.png")
    legendas.append(
        {
            "arquivo": "figura3_uf.png",
            "titulo": "Figura 3",
            "legenda": "Doze unidades da federação com mais contratos no corpus de análise.",
            "nota": (
                f"As demais unidades estão agregadas em resultados.json, chave por_uf. "
                f"Ordenação decrescente por n. Percentagens sobre N = {n_total}."
            ),
        }
    )

    # --- Figura 4: classes (decrescente por n; maior no topo) ---
    classes = sorted(ag["classificacao"], key=lambda row: row["n"])
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    id_to_idx = {cid: i for i, cid in enumerate(ORDEM_CLASSE)}
    bars_patches = []
    for row in classes:
        idx = id_to_idx.get(row["id"], 0)
        cor = _CORES_CLASSE[idx % len(_CORES_CLASSE)]
        bar = ax.barh(
            [row["rotulo"]],
            [row["n"]],
            color=cor,
            edgecolor="black",
            linewidth=0.6,
        )
        bars_patches.extend(bar)
    _anotar_barras_h(ax, bars_patches, n_total)
    ax.set_xlabel("Número de contratos")
    xmax = max((row["n"] for row in classes), default=0) * 1.32
    ax.set_xlim(0, xmax if xmax else 1)
    fig.tight_layout()
    _salvar(fig, "figura4_classes.png")
    legendas.append(
        {
            "arquivo": "figura4_classes.png",
            "titulo": "Figura 4",
            "legenda": "Classificação da destinação do contrato, por regras de prioridade.",
            "nota": (
                "A primeira classe que casa na descrição é a classe primária. Residual reúne "
                "descrições em que o léxico de inclusão aparece e nenhuma das oito classes casa. "
                f"Barras em ordem decrescente de n. Rótulos: n e percentagem do corpus (N = {n_total}). "
                "Cores Okabe–Ito (acessíveis a deficiência de visão de cores)."
            ),
        }
    )

    # --- Figura 5: classes × ano (empilhado colorido acessível) ---
    anos = [row["ano"] for row in ag["por_ano"]]
    totais_ano = {row["ano"]: row["n"] for row in ag["por_ano"]}
    base = [0] * len(anos)
    fig, ax = plt.subplots(figsize=(7.0, 4.6))
    for indice, row in enumerate(ag["classificacao"]):
        valores = [ag["por_classe_ano"][row["id"]].get(ano, 0) for ano in anos]
        cor = _CORES_CLASSE[indice % len(_CORES_CLASSE)]
        bars = ax.bar(
            anos,
            valores,
            bottom=base,
            label=f"{row['rotulo']} ({row['percentual']:.1f}%)",
            color=cor,
            edgecolor="black",
            linewidth=0.4,
        )
        texto = _cor_texto_sobre(cor)
        for patch, valor, ano, bottom in zip(bars, valores, anos, base):
            if valor <= 0:
                continue
            total_ano = totais_ano.get(ano, 0)
            # Anos com poucos contratos: rótulos internos sobrepõem-se — omitir.
            if total_ano < 200:
                continue
            if valor / max(total_ano, 1) < 0.08 or valor < 80:
                continue
            ax.text(
                patch.get_x() + patch.get_width() / 2,
                bottom + valor / 2,
                f"{_pct(valor, total_ano):.0f}%",
                ha="center",
                va="center",
                fontsize=7,
                color=texto,
                fontweight="bold",
            )
        base = [b + v for b, v in zip(base, valores)]
    ax.set_ylabel("Número de contratos")
    ax.set_xlabel("Ano de publicação no PNCP")
    ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1), fontsize=7)
    fig.tight_layout()
    _salvar(fig, "figura5_classes_ano.png")
    legendas.append(
        {
            "arquivo": "figura5_classes_ano.png",
            "titulo": "Figura 5",
            "legenda": "Classe primária de destinação, por ano de publicação no PNCP.",
            "nota": (
                "As faixas seguem a ordem fixa das classes. Cores Okabe–Ito "
                "(distinguíveis também para leitores com deficiência de visão de cores); "
                "texto interno preto ou branco conforme luminância do segmento. "
                "Rótulos internos: percentagem dentro do ano (segmentos pequenos omitidos). "
                "A legenda inclui a percentagem no corpus. 2026 é ano parcial. "
                "A Figura 4 traz a magnitude de cada classe."
            ),
        }
    )

    # --- Figura 6: modalidade (instrumento de contratação) ---
    mods = sorted(
        [row for row in ag["por_modalidade"] if row["n"] > 0],
        key=lambda row: row["n"],
    )
    fig, ax = plt.subplots(figsize=(7.0, 4.2))
    bars = ax.barh(
        [row["chave"] for row in mods],
        [row["n"] for row in mods],
        color=_COR_BARRA,
        edgecolor="black",
        linewidth=0.6,
    )
    _anotar_barras_h(ax, bars, n_total)
    ax.set_xlabel("Número de contratos")
    xmax = max((row["n"] for row in mods), default=0) * 1.28
    ax.set_xlim(0, xmax if xmax else 1)
    fig.tight_layout()
    _salvar(fig, "figura6_modalidade.png")
    legendas.append(
        {
            "arquivo": "figura6_modalidade.png",
            "titulo": "Figura 6",
            "legenda": "Contratos do corpus de análise, por modalidade de licitação.",
            "nota": (
                f"Campo modalidade_licitacao_nome do PNCP. Ordenação decrescente por n. "
                f"Percentagens sobre N = {n_total}."
            ),
        }
    )

    # --- Figura 7: associação classe × modalidade (% na classe) ---
    assoc = ag["associacao_classe_modalidade"]
    matriz = assoc["matriz_pct_na_classe"]
    classes_lbl = assoc["classes"]
    mods_lbl = assoc["modalidades"]
    fig, ax = plt.subplots(figsize=(8.2, 5.2))
    # Mapa sequencial azul (legível em escala de cinza parcial); valores anotados.
    import numpy as np

    data = np.array(matriz, dtype=float)
    im = ax.imshow(data, aspect="auto", cmap="Blues", vmin=0, vmax=100)
    ax.set_xticks(range(len(mods_lbl)), mods_lbl, rotation=35, ha="right", fontsize=8)
    ax.set_yticks(range(len(classes_lbl)), classes_lbl, fontsize=8)
    for i in range(data.shape[0]):
        for j in range(data.shape[1]):
            val = data[i, j]
            ax.text(
                j,
                i,
                f"{val:.0f}%",
                ha="center",
                va="center",
                fontsize=7,
                color="white" if val >= 45 else "black",
                fontweight="bold",
            )
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("% dentro da classe")
    ax.set_xlabel("Modalidade de licitação")
    ax.set_ylabel("Classe de destinação")
    fig.tight_layout()
    _salvar(fig, "figura7_classe_modalidade.png")
    top_txt = "; ".join(
        f"{c['classe']}→{c['modalidade']} (lift={c['lift']}, n={c['n']})"
        for c in assoc["associacoes_acima_do_acaso"][:5]
    )
    legendas.append(
        {
            "arquivo": "figura7_classe_modalidade.png",
            "titulo": "Figura 7",
            "legenda": (
                "Distribuição percentual da modalidade de licitação dentro de cada classe "
                "de destinação."
            ),
            "nota": (
                "Cada linha soma ~100%. Lift e resíduos em resultados.json "
                "(associacao_classe_modalidade). "
                f"Associações acima do acaso (amostra): {top_txt or 'nenhuma com n≥20 e lift≥1,2'}."
            ),
        }
    )
    return legendas


def _briefing(fluxo: dict, ag: dict, meta: dict) -> str:
    linhas_classe = "\n".join(
        f"| {row['rotulo']} | {row['n']} | {row['percentual']:.1f} |" for row in ag["classificacao"]
    )
    linhas_ano = "\n".join(f"| {row['ano']} | {row['n']} |" for row in ag["por_ano"])
    assoc = ag["associacao_classe_modalidade"]
    linhas_assoc = "\n".join(
        f"| {c['classe']} | {c['modalidade']} | {c['n']} | {c['pct_na_classe']:.1f} | {c['lift']} |"
        for c in assoc["associacoes_acima_do_acaso"][:12]
    ) or "| (nenhuma com n≥20 e lift≥1,2) | | | | |"
    return f"""# Pacote para redação do artigo

Escreva o artigo em português do Brasil. Este arquivo descreve um corpus já filtrado e classificado. Não recalcule as contagens. Use os números de `resultados.json`. As figuras estão em `figuras/`, PNG, 300 dpi, com paleta Okabe–Ito (acessível a deficiência de visão de cores), rótulos percentuais nas barras e sem título dentro da imagem. As legendas no padrão APA estão em `figuras/legendas.json` e devem ficar abaixo da figura.

## O que o estudo fez

Procurou no índice textual do PNCP (`GET /api/search/`) frases de inteligência artificial, entre 2021-01-01 e 2026-09-30. O corpus do artigo usa **apenas contratos** cuja descrição contém o léxico de inclusão, com um registo por `numero_controle_pncp`.

## Fluxo

| Etapa | N |
| --- | ---: |
| Documentos lidos na busca | {fluxo['documentos_lidos']} |
| Contratos lidos | {fluxo['contratos_lidos']} |
| Contratos com léxico na descrição | {fluxo['contratos_com_lexico_na_descricao']} |
| Contratos após deduplicação | {fluxo['contratos_apos_deduplicacao']} |

## Descritivo do corpus

Anos:

| Ano | N |
| --- | ---: |
{linhas_ano}

Esfera, UF e modalidade estão em `resultados.json`. Não some valores monetários. Reporte mediana e intervalo interquartil do valor global. Há valores extremos incompatíveis com um contrato isolado.

## Modalidade e associação com a destinação

A Figura 6 mostra as modalidades. A Figura 7 e a chave `associacao_classe_modalidade` em `resultados.json` cruzam classe × modalidade: percentagem **dentro da classe**, lift (= observado/esperado sob independência) e residual de Pearson. Use esses números; não invente que “capacitação = pregão” sem olhar a tabela — no corpus a capacitação tende a concentrar-se em **inexigibilidade** e **dispensa**, enquanto o **pregão eletrônico** aparece com mais força em classes de fornecimento (p.ex. reconhecimento facial, videomonitoramento).

Associações acima do acaso (lift ≥ 1,2 e n ≥ 20), topo:

| Classe | Modalidade | n | % na classe | Lift |
| --- | --- | ---: | ---: | ---: |
{linhas_assoc}

## Classificação

Regras em `src/analysis/destinacao_rules.yaml`, versão `{meta['classificador']}`, hash SHA-256 das regras `{meta['regras_sha256']}`. A primeira classe que casa ganha. Se o texto casa com mais de uma classe, as outras ficam em `classes_atingidas` no JSONL. Contratos com mais de uma classe atingida: {ag['com_mais_de_uma_classe']}.

| Classe | N | % |
| --- | ---: | ---: |
{linhas_classe}

Exemplos literais (amostra aleatória, semente 42, oito por classe) estão em `resultados.json`, chave `exemplos`. Não invente exemplos.

## Limitações para a discussão

- O endpoint de busca não está no Manual das APIs de Consultas. O total anunciado pelo índice não é o universo.
- A busca do portal casa palavras soltas. Por isso o artigo usa a frase na descrição, não o hit do portal.
- O corpus restringe-se a contratos; contratações só publicadas na fase convocatória ficam de fora.
- 2026 vai só até 30 de setembro.
- A classificação é lexical e determinística. Não é um modelo de tópicos. Um curso sobre reconhecimento facial fica em Capacitação, porque o objeto contratado é o curso.
- Residual não significa “não é inteligência artificial”. Significa que nenhuma das oito regras casou.
- Não reporte soma de valores.

## Como repetir

```
python -m analysis.export_artigo
```

Entrada: `data/raw/candidatas_search/hits.jsonl` (SHA-256 `{meta['hits_sha256']}`). Semente {SEED}. Python {meta['python']}.
"""


def exportar() -> None:
    rules = load_rules()
    rows, fluxo = montar_corpus(HITS, rules)
    ag = _agregar(rows, rules)
    OUT.mkdir(parents=True, exist_ok=True)
    FIG.mkdir(parents=True, exist_ok=True)
    meta = {
        "gerado_em_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "classificador": CLASSIFIER_VERSION,
        "regras_schema": rules.schema_version,
        "regras_sha256": rules.sha256,
        "hits_sha256": _sha256(HITS),
        "hits_caminho": "data/raw/candidatas_search/hits.jsonl",
        "janela": {"inicio": "2021-01-01", "fim": "2026-09-30"},
        "semente": SEED,
        "python": platform.python_version(),
        "plataforma": platform.platform(),
        "prioridade": "A primeira classe que casa na descrição é a classe primária.",
        "campo": "description",
        "unidade": "contrato",
        "deduplicacao": (
            "Apenas document_type=contrato. Um registo por numero_controle_pncp "
            "(fica a descrição mais longa se houver duplicata)."
        ),
        "classes": [
            {
                "id": rule.id,
                "rotulo": rule.rotulo,
                "priority": rule.priority,
                "definicao": rule.definicao,
                "patterns": [p.pattern for p in rule.compiled],
            }
            for rule in rules.classes
        ],
        "inclusao": [{"id": pid, "pattern": pattern.pattern} for pid, pattern in rules.inclusao],
    }
    (OUT / "metodologia.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "resultados.json").write_text(
        json.dumps({"fluxo": fluxo, **ag}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (OUT / "classificacao.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    legendas = _figuras(ag)
    (FIG / "legendas.json").write_text(json.dumps(legendas, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "briefing_claude.md").write_text(_briefing(fluxo, ag, meta), encoding="utf-8")
    print(json.dumps({"fluxo": fluxo, "classes": ag["classificacao"]}, ensure_ascii=True))


if __name__ == "__main__":
    sys.exit(exportar())
