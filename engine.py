"""SIDA/ELÚCIDA — motor 6.0 (triagem documental, não homologação).

Compatível com app.py existente: connect(), run_folder(folder, base_csv).
Somente PDFs fornecidos pelo usuário. Não altera a Base Geral.
"""
import csv
import hashlib
import io
import re
import sqlite3
import unicodedata
from pathlib import Path

import fitz

DB = "auditoria.sqlite3"
ENGINE_VERSION = "6.0-colunas-por-coordenadas-20261009"
YEARS = tuple(str(x) for x in range(2019, 2026))
MAT = re.compile(r"(?<!\d)\d{7,11}(?!\d)")
ACT = re.compile(r"^\s*(?:EDITAL|RESOLUCAO|PORTARIA|DECRETO|EXTRATO|AVISO|DESPACHO|ATO|REPUBLICACAO|RETIFICACAO)\b")
ADI = re.compile(r"\bADI\b|\bPGDI\b|AVALIACAO\s+(?:DE\s+)?DESEMPENHO|RESULTADO\s+(?:DA\s+)?AVALIACAO|NOTAS?\s+(?:DA\s+)?AVALIACAO")
KIND = {
    "ANULACAO": re.compile(r"\bANUL\w*|\bTORNA[R]?\s+SEM\s+EFEITO\b|\bDESCONSIDER\w*|\bCANCEL\w*"),
    "RETIFICACAO": re.compile(r"\bRETIFIC\w*|\bONDE\s+CONSTA\b|\bPASSE\s+A\s+CONSTAR\b|\bCORRIG\w*"),
    "INCLUSAO": re.compile(r"\bINCLU\w*|\bACRESCENT\w*"),
    "REPUBLICACAO": re.compile(r"\bREPUBLIC\w*"),
}
BAD = re.compile(r"\b(?:LICITACAO|PREGAO|CONTRATO|ORCAMENTARI[AO]|EMPENHO|NOTA\s+FISCAL|EXTRATO\s+DE\s+CONTRATO)\b")
YEAR_LABEL = re.compile(r"\b(?:EXERCICIO|ANO\s+(?:DA\s+)?AVALIACAO|ADI\s+(?:DE\s+)?|PGDI\s+(?:DE\s+)?|AVALIACAO\s+DE\s+DESEMPENHO\s+(?:DE\s+)?)[\s:–-]*(20(?:19|20|21|22|23|24|25))\b")
SCORE = re.compile(r"(?<![\w,.])(?:100(?:[,.]00)?|(?:[0-9]|[1-9][0-9])[,\.][0-9]{1,2}|C[0-9]{3})(?!\w)")
DOC_NUM = re.compile(r"(?<!\d)(1[012][._\s]?\d{3})(?!\d)")


def normalize(s):
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "").upper()) if not unicodedata.combining(c))


def connect():
    con = sqlite3.connect(DB, timeout=30)
    con.execute("PRAGMA busy_timeout=30000")
    con.execute("""CREATE TABLE IF NOT EXISTS docs (
      id TEXT PRIMARY KEY, name TEXT, numero INTEGER, tipo TEXT,
      pages INTEGER DEFAULT 0, done_pages INTEGER DEFAULT 0,
      status TEXT DEFAULT 'PENDENTE', error TEXT DEFAULT '')""")
    con.execute("""CREATE TABLE IF NOT EXISTS hits (
      doc TEXT, page INTEGER, tipo TEXT, matricula TEXT, servidor TEXT,
      exercicio TEXT, base_valor TEXT, trecho TEXT,
      situacao TEXT DEFAULT 'CANDIDATO - REVISAR',
      UNIQUE(doc,page,tipo,matricula,exercicio,trecho))""")
    con.execute("CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)")
    con.execute("""CREATE TABLE IF NOT EXISTS audit_details (
      doc TEXT, page INTEGER, matricula TEXT, exercicio TEXT,
      classificacao TEXT, codigo TEXT, nota_publicada TEXT,
      fonte_contexto TEXT, observacao TEXT,
      UNIQUE(doc,page,matricula,exercicio,fonte_contexto))""")
    version = con.execute("SELECT value FROM meta WHERE key='engine_version'").fetchone()
    if version is None or version[0] != ENGINE_VERSION:
        # Histórico anterior fica arquivado, sem misturar métricas antigas.
        con.execute("""CREATE TABLE IF NOT EXISTS history_docs AS SELECT *, '' AS version FROM docs WHERE 0""")
        con.execute("""CREATE TABLE IF NOT EXISTS history_hits AS SELECT *, '' AS version FROM hits WHERE 0""")
        if version is not None:
            con.execute("INSERT INTO history_docs SELECT *, ? FROM docs", (version[0],))
            con.execute("INSERT INTO history_hits SELECT *, ? FROM hits", (version[0],))
        con.execute("DELETE FROM audit_details")
        con.execute("DELETE FROM hits")
        con.execute("DELETE FROM docs")
        con.execute("INSERT OR REPLACE INTO meta VALUES ('engine_version',?)", (ENGINE_VERSION,))
    con.commit()
    return con


def identity(path):
    name = Path(path).name
    m = DOC_NUM.search(name)
    number = int(re.sub(r"\D", "", m.group(1))) if m else 99999
    typ = ("SUPLEMENTO" if "SUP" in name.upper() else
           "EXTRA" if "EXTRA" in name.upper() else "PRINCIPAL")
    digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    return digest, number, typ


def load_base_csv(path):
    raw = Path(path).read_bytes()
    if not raw:
        raise ValueError("Base Geral CSV vazio.")
    encodings = (("utf-16",) if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else
                 ("utf-8-sig", "cp1252") if not raw.startswith(b"\xef\xbb\xbf") else
                 ("utf-8-sig",))
    content = None
    for enc in encodings:
        try:
            content = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if content is None:
        raise ValueError("Codificação da Base Geral não reconhecida.")
    first = next((line for line in content.splitlines() if line.strip()), "")
    delimiter = max((";", "\t", ","), key=first.count)
    reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
    headers = {normalize(x).strip() for x in (reader.fieldnames or []) if x}
    if not {"MATRICULA", "SERVIDOR"}.issubset(headers):
        raise ValueError("A Base Geral precisa ter MATRÍCULA e SERVIDOR como cabeçalhos.")
    base = {}
    for record in reader:
        row = {normalize(k).strip(): str(v or "").strip() for k, v in record.items() if k}
        mat = re.sub(r"\D", "", row.get("MATRICULA", ""))
        if mat:
            base[mat] = row
    if not base:
        raise ValueError("Nenhuma matrícula encontrada na Base Geral.")
    return base


def year_context(text):
    years = set(YEAR_LABEL.findall(normalize(text)))
    return next(iter(years)) if len(years) == 1 else "INDETERMINADO"


def matches_name(text, name):
    words = [w for w in normalize(name).split() if len(w) >= 3 and w not in {"DOS", "DAS"}]
    text = " " + normalize(text) + " "
    return bool(words) and sum(bool(re.search(r"\b" + re.escape(w) + r"\b", text)) for w in words) >= min(2, len(words))



def visual_rows(page, tolerance=3.3):
    """Agrupa palavras por linha visual usando posição vertical real."""
    words = sorted(page.get_text("words"), key=lambda w: ((w[1]+w[3])/2, w[0]))
    rows = []
    for word in words:
        x0, y0, x1, y1, token, *_ = word
        cy = (y0+y1)/2
        if rows and abs(rows[-1]["y"] - cy) <= tolerance:
            rows[-1]["words"].append((x0,x1,str(token)))
        else:
            rows.append({"y":cy,"words":[(x0,x1,str(token))]})
    for row in rows:
        row["words"].sort(key=lambda w:w[0])
        row["text"]=" ".join(w[2] for w in row["words"])
    return rows


def column_headers(row):
    """Anos explicitamente escritos numa linha de cabeçalho e posições X.

    Recusa anos repetidos, datas e mais de um ano na mesma célula.
    """
    line = normalize(row["text"])
    if re.search(r"\b(?:PUBLICACAO|DIARIO OFICIAL|DATA|DOE)\b",line):
        return {}
    if not (re.search(r"\b(?:NOTA|AVALIACAO|EXERCICIO|MEDIA|ANO|2019|2020|2021|2022|2023|2024|2025)\b",line)):
        return {}
    found={}
    for x0,x1,word in row["words"]:
        w=normalize(word).strip(".:;()[]")
        if w in YEARS:
            if w in found:
                return {}
            found[w]=(x0+x1)/2
    return found if len(found)>=2 else {}


def aligned_scores(row, header):
    """Mapeia SOMENTE valores visualmente alinhados a anos explícitos.

    Não atribui média nem código sem coluna própria e não converte Cxxx.
    """
    if not header:
        return {}
    years=sorted(header, key=lambda y:header[y])
    centers=[header[y] for y in years]
    result={}
    for x0,x1,token in row["words"]:
        val=normalize(token).strip(";:|[]()")
        if not re.fullmatch(r"(?:100(?:[,\.]00)?|(?:[0-9]|[1-9][0-9])[,\.][0-9]{1,2}|C[0-9]{3})",val):
            continue
        cx=(x0+x1)/2
        k=min(range(len(centers)),key=lambda j:abs(cx-centers[j]))
        # Rejeita valores fora das faixas dos anos e alinhamentos ambíguos.
        distances=sorted(abs(cx-c) for c in centers)
        if distances[0]>32 or (len(distances)>1 and distances[1]-distances[0]<8):
            continue
        year=years[k]
        if year in result:
            result[year]=None  # mais de um valor na mesma coluna
        else:
            result[year]=val
    return {year:val for year,val in result.items() if val is not None}


def extract_candidates(page, base, inherited=None):
    rows=visual_rows(page)
    context={"adi":False,"kind":None,"year":"INDETERMINADO","header":""}
    recent=[]
    header_columns={}
    header_y=-1000
    for idx,row in enumerate(rows):
        line=normalize(row["text"])
        recent=(recent+[line])[-24:]
        if ACT.search(line):
            context={"adi":False,"kind":None,"year":"INDETERMINADO","header":line}
            header_columns={}
            recent=[line]
        if ADI.search(line):
            context["adi"]=True
            context["header"]=(context["header"]+" | "+line)[-1100:]
        for label,pattern in KIND.items():
            if pattern.search(line):
                context["kind"]=label
                context["header"]=(context["header"]+" | "+line)[-1100:]
                break
        explicit=year_context(" ".join(recent))
        if explicit!="INDETERMINADO":
            context["year"]=explicit
        if BAD.search(line):
            continue
        # Cabeçalho válido precisa estar na seção de ADI/PGDI.
        columns=column_headers(row)
        if context["adi"] and columns:
            header_columns=columns
            header_y=row["y"]
        if not (context["adi"] and context["kind"]):
            continue
        mats=list(dict.fromkeys(m for m in MAT.findall(line) if m in base))
        if len(mats)!=1:
            continue
        mat=mats[0]
        person=base[mat].get("SERVIDOR","")
        if not matches_name(line,person):
            continue
        own=line[line.find(mat):]
        if not matches_name(own,person):
            continue
        # Cabeçalho de colunas só vale abaixo dele e até distância limitada.
        mapped=aligned_scores(row,header_columns) if 0 < row["y"]-header_y < 500 else {}
        if mapped:
            items=[(year,value) for year,value in sorted(mapped.items())]
        else:
            year=year_context(line)
            if year=="INDETERMINADO":
                year=context["year"]
            items=[(year,"")]
        for year,value in items:
            status=("PENDENTE - VALIDAR COLUNA E ATO" if value else
                    "PENDENTE - EXERCICIO/COLUNAS")
            yield {"tipo":context["kind"],"matricula":mat,"servidor":person,
                "ano":year,"base_valor":base[mat].get("NOTA "+year,"") if year in YEARS else "",
                "trecho":row["text"][:1300],
                "nota":value if value and not value.startswith("C") else "",
                "codigo":value if value.startswith("C") else "",
                "status":status,
                "contexto":(context["header"]+" | COLUNAS: "+str(header_columns))[:1000]}

def scan_one(path, base):
    con = connect()
    digest, number, typ = identity(path)
    previous = con.execute("SELECT status,done_pages FROM docs WHERE id=?", (digest,)).fetchone()
    if previous and previous[0] in ("EXTRACAO CONCLUIDA - REVISAR", "CONCLUIDO"):
        con.close()
        return "já extraído nesta versão; pendente de validação"
    con.execute("INSERT OR IGNORE INTO docs(id,name,numero,tipo) VALUES (?,?,?,?)",
                (digest, Path(path).name, number, typ))
    con.commit()
    try:
        with fitz.open(path) as pdf:
            total = len(pdf)
            con.execute("UPDATE docs SET pages=?,status='EM ANALISE',error='' WHERE id=?", (total, digest))
            con.commit()
            start = min(previous[1], total) if previous else 0
            for i in range(start, total):
                page = pdf[i]
                if not page.get_text("text").strip():
                    # PDF imagem: marcar incompleto em vez de afirmar leitura total.
                    con.execute("UPDATE docs SET status='PESQUISA INCOMPLETA',error=? WHERE id=?",
                                (f"Página {i+1} sem texto extraível (possível digitalização)", digest))
                    con.commit()
                    return "pesquisa incompleta: página sem texto extraível"
                for item in extract_candidates(page, base):
                    con.execute("""INSERT OR IGNORE INTO hits
                      (doc,page,tipo,matricula,servidor,exercicio,base_valor,trecho,situacao)
                      VALUES (?,?,?,?,?,?,?,?,?)""",
                      (digest, i + 1, item["tipo"], item["matricula"], item["servidor"],
                       item["ano"], item["base_valor"], item["trecho"], item["status"]))
                    con.execute("""INSERT OR IGNORE INTO audit_details
                      (doc,page,matricula,exercicio,classificacao,codigo,nota_publicada,fonte_contexto,observacao)
                      VALUES (?,?,?,?,?,?,?,?,?)""",
                      (digest, i + 1, item["matricula"], item["ano"], item["tipo"],
                       item["codigo"], item["nota"], item["contexto"],
                       "Triagem automática; verificar cabeçalho, linha, código e versões anteriores/posteriores"))
                con.execute("UPDATE docs SET done_pages=? WHERE id=?", (i + 1, digest))
                con.commit()
            con.execute("UPDATE docs SET status='EXTRACAO CONCLUIDA - REVISAR' WHERE id=?", (digest,))
            con.commit()
        return "extração concluída, pendente de validação"
    except Exception as exc:
        con.execute("UPDATE docs SET status='ERRO',error=? WHERE id=?", (str(exc)[:500], digest))
        con.commit()
        return f"erro: {exc}"
    finally:
        con.close()


def run_folder(folder, base_csv):
    paths = list(Path(folder).glob("*.pdf"))
    ordered = sorted(paths, key=lambda p: (identity(p)[1], {"PRINCIPAL":0,"SUPLEMENTO":1,"EXTRA":2}[identity(p)[2]], p.name))
    base = load_base_csv(base_csv)
    base_hash = hashlib.sha256(Path(base_csv).read_bytes()).hexdigest()
    con = connect()
    old = con.execute("SELECT value FROM meta WHERE key='base_hash'").fetchone()
    if old and old[0] != base_hash:
        # Candidatos calculados contra outra base não podem ser reaproveitados.
        con.execute("DELETE FROM audit_details")
        con.execute("DELETE FROM hits")
        con.execute("DELETE FROM docs")
    con.execute("INSERT OR REPLACE INTO meta VALUES ('base_hash',?)", (base_hash,))
    con.commit()
    con.close()
    seen = set()
    for path in ordered:
        digest = identity(path)[0]
        if digest in seen:
            continue
        seen.add(digest)
        yield path.name, scan_one(path, base)
