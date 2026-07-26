<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/yeer0s/recibosegarantia/main/docs/images/recibos-wide-dark-1k.svg">
    <img alt="Recibos e Garantia" src="https://raw.githubusercontent.com/yeer0s/recibosegarantia/main/docs/images/recibos-wide-light-1k.svg" width=58%>
  </picture>
</p>

<p align="center">
  <a href="https://github.com/yeer0s/recibosegarantia/actions/workflows/gates.yml"><img src="https://github.com/yeer0s/recibosegarantia/actions/workflows/gates.yml/badge.svg" alt="gates"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licen%C3%A7a-MIT-green.svg" alt="MIT"></a>
  <img src="https://img.shields.io/badge/rede-zero%20chamadas-00a8a8" alt="offline">
  <img src="https://img.shields.io/badge/depend%C3%AAncias-s%C3%B3%20stdlib-00a8a8" alt="sem dependências">
  <img src="https://img.shields.io/badge/fixtures-oficiais%20da%20AT-orange" alt="fixtures oficiais">
  <a href="https://mowei.pt"><img src="https://img.shields.io/badge/por-mowei.pt-111111" alt="mowei.pt"></a>
  <a href="https://buymeacoffee.com/letsmoweis"><img src="https://img.shields.io/badge/%E2%98%95-paga--me%20um%20caf%C3%A9-FFDD00" alt="Paga-me um café"></a>
  <a href="https://ko-fi.com/letsmowei"><img src="https://img.shields.io/badge/ko--fi-apoiar-FF5E5B" alt="Ko-fi"></a>
</p>

<h3 align="center">
  Fotografa o talão.<br>
  Fica estruturado, validado, avisado.<br>
  Nada sai da tua máquina.
</h3>

<p align="center">
  <b>Captura, validação e controlo de garantias de recibos, offline.</b><br>
  Descodifica o código QR obrigatório · reconcilia contra os exemplos da própria<br>
  Autoridade Tributária · diz-te quando a garantia acaba mesmo.<br>
  <sub><a href="README.md">🇬🇧 Read in English</a></sub>
</p>

---

:fire: ***Novidades*** :fire:

- **[Jul 2026]** Primeira versão pública — descodificação QR, validação, garantias, exportação iCal
- **[Jul 2026]** As fixtures são os **quatro exemplos oficiais da AT**, não casos inventados
- **[Jul 2026]** Modelo de campos completo: `I*` continente, `J*` Açores, `K*` Madeira, `L` não sujeito, `M` imposto do selo, `P` retenções — uma versão anterior só conhecia `I*` e reconciliava mal todas as faturas regionais
- **[Jul 2026]** Duas datas de garantia por compra, porque o DL 84/2021 tem duas — e a que ninguém conhece é a dos 2 anos
- **[Jul 2026]** Companheira do [Ao Cêntimo](https://github.com/yeer0s/AoCentimo), o motor de IRS offline

---

## Os teus recibos não são da conta de nenhuma API

A fotografia de um talão leva mais do que números: o teu nome, a tua morada, a farmácia
onde foste, o que te trataram. Todos os "scanners de recibos com IA" enviam isso para o
servidor de outra pessoa.

**Este não tem caminho no código que o pudesse fazer.**

<p align="center">
  <img src="docs/images/gates.svg" alt="gates a passar" width=74%>
</p>

- **Zero chamadas de rede.** O `scripts/offline_audit.py` analisa cada ficheiro e falha
  perante qualquer import de rede, `subprocess` ou `ctypes`, qualquer chamada ao sistema
  (`os.system`, `os.popen`, `os.exec*`), qualquer import dinâmico e qualquer `eval`/`exec`
  nativo. O CI corre **todos os gates com a camada de sockets desativada**.
- **Sem dependências.** Biblioteca padrão do Python 3.10+. O `openpyxl` é opcional: sem
  ele obténs CSV com as mesmas colunas.
- **Corre num modelo local.** Ollama, llama.cpp, LM Studio, uma máquina isolada.
- **Estrutural, não prometida.** Com precisão: a auditoria é uma *verificação estática, não
  uma sandbox*. Apanha o acidental e o óbvio, não um contribuidor malicioso determinado.
  Ver [SECURITY.md](SECURITY.md).

## Como funciona

<p align="center">
  <img src="docs/images/pipeline.svg" alt="pipeline" width=92%>
</p>

Desde a **Portaria n.º 195/2020** todas as faturas portuguesas levam um código QR com os
campos em *dados estruturados* — NIFs, data, número, ATCUD, decomposição de IVA, totais.
Descodificar é local, imediato e **não pode alucinar**. O OCR é o recurso para talões
anteriores a 2022 e papel térmico desbotado, nunca o caminho principal.

## As duas coisas que se recusa a fazer

**Nunca adivinha o que compraste.** Não existe campo para isso — nem na Portaria 195/2020
nem em lado nenhum. O QR leva *quem, quando, quanto e a repartição do imposto*. Todos os
indícios falham: 23% de IVA cobre a maioria dos bens **e** dos serviços; `FT`/`FS` são
formatos de faturação; uma oficina vende peças e mão de obra na mesma fatura. Por isso
`tipo` fica em `por_classificar` e **nenhuma data de garantia é produzida até alguém dizer
o que foi.** Três anos aplicados a tudo diriam que o teu corte de cabelo está garantido até
2029 — um prazo que não existe.

**Recusa faturas empresariais.** Uma fatura passada a uma empresa envolve *IVA dedutível* e
o regime de garantia comercial, não o do consumidor. Outro domínio, outro risco: a skill
pára em vez de produzir números confiantes e errados.

## Garantia: duas datas, não uma

<p align="center">
  <img src="docs/images/garantia.svg" alt="duas datas de garantia" width=88%>
</p>

Verificado contra o texto consolidado do **DL 84/2021**, porque "dois anos" é a resposta
habitual e está **errada para Portugal**:

| Tipo | Responsabilidade | Presunção | Artigo |
|---|---|---|---|
| Bem móvel novo | **3 anos** | 2 anos | 12.º n.º 1 · 13.º n.º 1 |
| Bem móvel usado | 3 anos, reduzível a **18 meses** por acordo expresso | 2 anos | 12.º n.º 3 |
| Recondicionado | 3 anos, menção obrigatória na fatura | 2 anos | 12.º |
| Bem imóvel | 10 anos estrutural / 5 anos restantes | 2 anos | 23.º n.º 1 |
| **Serviço comum** | **fora do âmbito do DL 84/2021** | — | 1.º |

Nos primeiros 2 anos é o **vendedor** que tem de provar que o defeito não existia na
entrega. Dos 2 aos 3 continuas a ter direitos, mas a prova passa a ser **tua** — o mesmo
recibo, uma posição materialmente mais fraca. É por isso que o calendário emite **dois**
eventos por compra.

**Não há prazo para denunciar o defeito** (art. 12.º n.º 5, abolido) — mas depois de
denunciares, os direitos caducam **2 anos** depois (art. 17.º n.º 1).

## Instalação

```bash
git clone https://github.com/yeer0s/recibosegarantia.git
cp -r recibosegarantia ~/.claude/skills/recibos-e-garantia
```

## Verifica tu mesmo, em 30 segundos

```bash
cd recibosegarantia
python scripts/fatura.py --selftest        # exemplos da AT + 22 casos adversariais
python scripts/garantia.py --selftest      # prazos DL 84/2021 + iCal RFC 5545
python scripts/planilha.py --selftest      # três folhas, fallback CSV
python scripts/offline_audit.py --selftest # provar que a auditoria consegue falhar
python scripts/sweep.py                    # 56 verificações
```

Todos saem com `0`. Experimenta com o Wi-Fi desligado.

## Porque confiar nesta

**As fixtures foram escritas pela Autoridade Tributária, não por nós.** Os quatro casos em
`assets/at-examples.json` são transcritos literalmente da secção 5 da especificação do QR
da AT. O exemplo 1 abrange continente + Açores + Madeira + imposto do selo + retenção e
reconcilia em **513 600,58 €** exatamente.

Isto importa porque o projeto irmão [Ao Cêntimo](https://github.com/yeer0s/AoCentimo)
lançou um corpus inteiramente derivado de si próprio, e ficou cego a uma taxa revogada
durante um ano com todos os testes verdes. **Um corpus derivado daquilo que verifica não te
consegue falhar, e é esse o problema.** Este consegue.

| Garantia | Como é imposta |
|---|---|
| **Uma verificação que não corre TEM de sinalizar, nunca saltar** | Um valor ilegível desativava silenciosamente toda a verificação aritmética, deixando passar 9 999 999,99 € sem um único aviso. Agora cada ramo "não consegue avaliar" sinaliza |
| **Um validador pode REJEITAR; nunca CONFIRMAR** | O dígito de controlo do NIF deixa passar 1,53% das corrupções de um dígito — `100000010` e `600000010` diferem num dígito e ambos são válidos |
| **A proveniência viaja com o valor** | Um campo do QR é uma transcrição; um campo de OCR é uma leitura. Nunca chegam à folha com a mesma confiança |
| **Cada lacuna declara a direção do erro** | A bateria falha se alguma não a tiver |

A reconciliação, verificada ao cêntimo contra os quatro exemplos oficiais:

```
N = Σ(IVA: I4,I6,I8 · J4,J6,J8 · K4,K6,K8) + M (imposto do selo)
O = Σ(bases: I2,I3,I5,I7 · J2,J3,J5,J7 · K2,K3,K5,K7) + L (não sujeito) + N
P (retenções na fonte) NÃO faz parte de O
```

Uma versão anterior, feita a partir de um blogue e não da especificação, só conhecia os
campos `I*` — e reconciliava mal **todas** as faturas dos Açores, da Madeira, com imposto
do selo ou com retenção, além de tratar `N` como só IVA quando é IVA **mais** imposto do selo.

## Resultado

| Folha | Conteúdo |
|---|---|
| `RECIBOS` | todas as faturas, todos os campos, avisos em coluna própria |
| `GARANTIAS` | só bens, as duas datas, base legal, avisos |
| `REVISAO` | tudo o que foi sinalizado — para as linhas partidas não se esconderem entre as boas |

Mais `garantias.ics` (RFC 5545, dois eventos por compra, 30 dias de antecedência, alarme) e
um JSON que o [Ao Cêntimo](https://github.com/yeer0s/AoCentimo) importa diretamente.

## ⚠️ Não é aconselhamento fiscal nem jurídico

**Isto é uma leitura automática de um documento, não um parecer profissional, e não cria
qualquer relação profissional. Confirma todos os valores com um contabilista certificado
(OCC) antes de entregar seja o que for, e confirma todos os prazos de garantia com o
vendedor ou a [DECO](https://www.deco.proteste.pt/) antes de reclamar.**

Apenas a [Autoridade Tributária](https://info.portaldasfinancas.gov.pt) e o Diário da
República são autoritativos. Uma calculadora não assina o teu Modelo 3, não te representa
nas Finanças e não faz uma reclamação de garantia por ti. Termos completos:
**[DISCLAIMER.md](DISCLAIMER.md)**.

## Gratuito, e vai continuar

MIT. Sem versão paga, sem muro de email, sem telemetria.

Feito por **[mowei.pt](https://mowei.pt)** — ferramentas de comparação gratuitas e guias em
português simples para energia, telecomunicações, seguros, banca, crédito e apoios.

<p align="center">
  <a href="https://mowei.pt"><img src="docs/images/mowei-banner.svg" alt="mowei.pt" width=80%></a>
</p>

<p align="center">
  <a href="https://mowei.pt"><b>🇵🇹 mowei.pt — ferramentas gratuitas</b></a>
  &nbsp;·&nbsp;
  <a href="https://buymeacoffee.com/letsmoweis"><img src="https://img.shields.io/badge/%E2%98%95-Paga--me%20um%20caf%C3%A9-FFDD00?style=for-the-badge" alt="Paga-me um café"></a>
  &nbsp;·&nbsp;
  <a href="https://ko-fi.com/letsmowei"><img src="https://img.shields.io/badge/Ko--fi-apoiar-FF5E5B?style=for-the-badge&logo=ko-fi&logoColor=white" alt="Ko-fi"></a>
</p>

O apoio é totalmente opcional e sempre será — o projeto está completo sem ele.

## Contribuir

Por ordem de valor:

1. **Um número ou uma citação errada** — um prazo, artigo ou semântica de campo que
   contradiga a fonte que cita. A coisa mais valiosa que podes enviar.
2. **OCR para talões sem código QR** — anteriores a 2022 e térmicos desbotados, hoje só por
   introdução manual.
3. **Estado do documento `F`/`S`/`R`** — a consequência para a dedução não está estabelecida
   a partir de fonte primária, por isso são sinalizados e nunca confiados.
4. **Autenticidade do QR** — `Q`/`R` são lidos e nunca verificados.

Todos os PRs mantêm os gates a sair com `0`, e cada constante nova precisa da sua citação.

## Licença

[MIT](LICENSE) — usa, faz fork, distribui comercialmente. Um link de volta para
[mowei.pt](https://mowei.pt) é apreciado, nunca exigido.
