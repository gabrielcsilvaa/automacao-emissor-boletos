
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Dict, Iterable, List, Union

from .enums import SINDICATOS, SINDICATO_TIPOS_CONTRIBUICAO, TipoContribuicao
from .models import BoletoRequest, Competencia


@dataclass(frozen=True)
class ValidationError(Exception):
    """
    Erro de validação com mensagens por campo (bom pra UI).
    Ex.: raise ValidationError({"cnpj": "CNPJ inválido", "valor": "Valor obrigatório"})
    """
    errors: Dict[str, str]

    def __str__(self) -> str:
        return "ValidationError(" + ", ".join(f"{k}={v}" for k, v in self.errors.items()) + ")"


@dataclass(frozen=True)
class BatchValidationError(Exception):
    """
    Erro de validacao para lotes.
    Ex.: {0: {"cnpj": "invalido"}, 3: {"valor": "obrigatorio"}}
    """
    errors: Dict[int, Dict[str, str]]

    def __str__(self) -> str:
        parts = []
        for idx, item_errors in self.errors.items():
            detail = ", ".join(f"{k}={v}" for k, v in item_errors.items())
            parts.append(f"item[{idx}]({detail})")
        return "BatchValidationError(" + "; ".join(parts) + ")"


# ---------------------------
# Helpers gerais
# ---------------------------

def only_digits(text: str) -> str:
    return "".join(ch for ch in (text or "") if ch.isdigit())


def normalize_text(text: str) -> str:
    return (text or "").strip()


# ---------------------------
# CNPJ
# ---------------------------

def is_valid_cnpj(cnpj: str) -> bool:
    """
    Valida CNPJ (14 dígitos + dígitos verificadores).
    Aceita CNPJ com máscara também.
    """
    d = only_digits(cnpj)

    if len(d) != 14:
        return False

    # Rejeita CNPJ com todos dígitos iguais (ex.: 00000000000000)
    if d == d[0] * 14:
        return False

    base = d[:12]
    dv = d[12:]

    dv1 = _calc_cnpj_dv(base)
    dv2 = _calc_cnpj_dv(base + dv1)

    return dv == (dv1 + dv2)


def _calc_cnpj_dv(base_12_or_13: str) -> str:
    """
    Calcula 1 dígito verificador do CNPJ.
    """
    weights_12 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    weights_13 = [6] + weights_12

    weights = weights_12 if len(base_12_or_13) == 12 else weights_13
    total = 0
    for digit, w in zip(base_12_or_13, weights):
        total += int(digit) * w

    mod = total % 11
    dv = 0 if mod < 2 else 11 - mod
    return str(dv)


# ---------------------------
# Valor monetário (PT-BR e afins)
# ---------------------------

def parse_money(value: Union[str, int, float, Decimal]) -> Decimal:
    """
    Aceita:
    - "1.234,56" (pt-BR)
    - "1234,56"
    - "1234.56"
    - "R$ 1.234,56"
    - 1234, 1234.56, Decimal(...)
    Retorna Decimal com 2 casas.
    """
    if isinstance(value, Decimal):
        dec = value
    elif isinstance(value, (int, float)):
        # cuidado com float: converte via str para reduzir erro
        dec = Decimal(str(value))
    else:
        raw = normalize_text(str(value))
        raw = raw.replace("R$", "").replace(" ", "")

        if raw == "":
            raise ValueError("Valor vazio.")

        # Detecta separador decimal pelo último separador (',' ou '.')
        last_comma = raw.rfind(",")
        last_dot = raw.rfind(".")

        if last_comma > last_dot:
            # pt-BR típico: '.' milhar, ',' decimal
            raw = raw.replace(".", "")
            raw = raw.replace(",", ".")
        else:
            # formato tipo en-US: ',' milhar, '.' decimal (ou só '.')
            # remove ',' como milhar
            raw = raw.replace(",", "")

        try:
            dec = Decimal(raw)
        except InvalidOperation:
            raise ValueError("Valor inválido. Ex.: 1234,56")

    # Normaliza para 2 casas
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ---------------------------
# Mês / Ano
# ---------------------------

def parse_int(value: Any, field_name: str) -> int:
    if value is None:
        raise ValueError(f"{field_name} vazio.")
    if isinstance(value, int):
        return value
    s = normalize_text(str(value))
    if s == "":
        raise ValueError(f"{field_name} vazio.")
    try:
        return int(s)
    except ValueError:
        raise ValueError(f"{field_name} inválido.")


def validate_competencia(ano: Any, mes: Any) -> Competencia:
    y = parse_int(ano, "ano")
    m = parse_int(mes, "mes")

    if y < 2000 or y > 2100:
        raise ValueError("Ano fora do intervalo esperado (2000..2100).")
    if m < 1 or m > 12:
        raise ValueError("Mês inválido. Use 1..12.")

    return Competencia(ano=y, mes=m)


# ---------------------------
# Tipo de contribuição / Sindicato
# ---------------------------

def parse_tipo_contribuicao(value: Any) -> TipoContribuicao:
    """
    Aceita:
    - TipoContribuicao (Enum)
    - string igual ao .value do Enum (texto do dropdown)
    """
    if isinstance(value, TipoContribuicao):
        return value

    s = normalize_text(str(value))
    for t in TipoContribuicao:
        if s == t.value:
            return t

    raise ValueError("Tipo de contribuição inválido.")


def validate_sindicato_key(sindicato_key: Any) -> str:
    key = normalize_text(str(sindicato_key))
    if key == "":
        raise ValueError("Sindicato obrigatório.")
    if key not in SINDICATOS:
        raise ValueError("Sindicato inválido.")
    return key


# ---------------------------
# Validação completa: cria o BoletoRequest
# ---------------------------

def validar_e_montar_request(
    *,
    sindicato_key: Any,
    tipo_contribuicao: Any,
    cnpj: Any,
    senha: Any,
    valor: Any,
    ano: Any,
    mes: Any,
) -> BoletoRequest:
    """
    Valida campos (com mensagens por campo) e retorna um BoletoRequest pronto.
    Se tiver erro, levanta ValidationError({campo: mensagem}).
    """
    errors: Dict[str, str] = {}

    s_key = ""
    t_contrib: TipoContribuicao | None = None

    # sindicato
    try:
        s_key = validate_sindicato_key(sindicato_key)
    except ValueError as e:
        errors["sindicato_key"] = str(e)

    # tipo
    try:
        t_contrib = parse_tipo_contribuicao(tipo_contribuicao)
    except ValueError as e:
        errors["tipo_contribuicao"] = str(e)

    # compatibilidade sindicato x tipo
    if s_key and t_contrib is not None:
        allowed = SINDICATO_TIPOS_CONTRIBUICAO.get(s_key, [])
        if allowed and t_contrib not in allowed:
            errors["tipo_contribuicao"] = "Tipo não permitido para o sindicato selecionado."

    # cnpj
    cnpj_str = normalize_text(str(cnpj))
    if cnpj_str == "":
        errors["cnpj"] = "CNPJ obrigatório."
    elif not is_valid_cnpj(cnpj_str):
        errors["cnpj"] = "CNPJ inválido."

    # senha
    senha_str = normalize_text(str(senha))
    if senha_str == "":
        errors["senha"] = "Senha obrigatória."

    # valor
    try:
        v = parse_money(valor)
        if v <= Decimal("0.00"):
            errors["valor"] = "Valor deve ser maior que zero."
    except ValueError as e:
        errors["valor"] = str(e)

    # competência
    try:
        comp = validate_competencia(ano, mes)
    except ValueError as e:
        errors["competencia"] = str(e)

    if errors:
        raise ValidationError(errors)

    # Tudo ok, monta o request
    return BoletoRequest(
        sindicato_key=s_key,
        tipo_contribuicao=t_contrib,
        cnpj=cnpj_str,
        senha=senha_str,
        valor=v,
        competencia=comp,
    )


def ordenar_requests_por_sindicato(requests: Iterable[BoletoRequest]) -> List[BoletoRequest]:
    """
    Agrupa requests por sindicato, preservando:
    - ordem de primeira aparicao de cada sindicato
    - ordem original dentro de cada sindicato
    """
    grouped: Dict[str, List[BoletoRequest]] = {}
    sindicato_order: List[str] = []

    for req in requests:
        key = req.sindicato_key
        if key not in grouped:
            grouped[key] = []
            sindicato_order.append(key)
        grouped[key].append(req)

    ordered: List[BoletoRequest] = []
    for key in sindicato_order:
        ordered.extend(grouped[key])
    return ordered


def validar_e_montar_requests(
    requests: Any,
    *,
    ordenar_por_sindicato: bool = True,
) -> List[BoletoRequest]:
    """
    Valida uma colecao de requests (lista de dicts) para uso no front.

    Cada item deve ter as mesmas chaves de `validar_e_montar_request`.
    Se houver erro em qualquer item, levanta BatchValidationError com os
    campos invalidos por indice.
    """
    if requests is None:
        raise BatchValidationError({0: {"request": "Lista de requests obrigatoria."}})

    if isinstance(requests, (str, bytes, dict)):
        raise BatchValidationError({0: {"request": "Use uma lista de requests."}})

    try:
        raw_items = list(requests)
    except TypeError:
        raise BatchValidationError({0: {"request": "Formato invalido para lote de requests."}})

    if not raw_items:
        raise BatchValidationError({0: {"request": "Informe pelo menos uma request."}})

    built: List[BoletoRequest] = []
    batch_errors: Dict[int, Dict[str, str]] = {}

    for idx, item in enumerate(raw_items):
        if isinstance(item, BoletoRequest):
            built.append(item)
            continue

        if not isinstance(item, dict):
            batch_errors[idx] = {"request": "Cada item deve ser um objeto (dict)."}
            continue

        try:
            req = validar_e_montar_request(
                sindicato_key=item.get("sindicato_key"),
                tipo_contribuicao=item.get("tipo_contribuicao"),
                cnpj=item.get("cnpj"),
                senha=item.get("senha"),
                valor=item.get("valor"),
                ano=item.get("ano"),
                mes=item.get("mes"),
            )
            built.append(req)
        except ValidationError as e:
            batch_errors[idx] = e.errors

    if batch_errors:
        raise BatchValidationError(batch_errors)

    if ordenar_por_sindicato:
        return ordenar_requests_por_sindicato(built)
    return built


# ---------------------------
# Utilidade: normalizar CNPJ para salvar em pasta
# ---------------------------

def cnpj_digits_or_raise(cnpj: str) -> str:
    """
    Retorna apenas os 14 dígitos do CNPJ (bom pra usar em pasta/arquivo).
    """
    d = only_digits(cnpj)
    if len(d) != 14 or not is_valid_cnpj(d):
        raise ValueError("CNPJ inválido.")
    return d
