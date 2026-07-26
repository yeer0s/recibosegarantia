# Não é aconselhamento fiscal nem jurídico · Not tax or legal advice

**Recibos e Garantia faz uma LEITURA AUTOMÁTICA de documentos, a partir de especificações
públicas e de legislação pública. Não é aconselhamento fiscal, jurídico, contabilístico ou
financeiro, e não cria qualquer relação profissional.**

## Antes de agir com base em qualquer resultado

**Todos os valores extraídos têm de ser confirmados por um contabilista certificado (OCC)
antes de entregar, assinar ou pagar seja o que for. Todos os prazos de garantia têm de ser
confirmados com o vendedor, com a DECO ou com um jurista antes de fazer uma reclamação.**

Não é formalidade. Uma calculadora não pode:

- assinar o seu Modelo 3
- representá-lo perante a Autoridade Tributária
- fazer uma reclamação de garantia em seu nome
- ter seguro de responsabilidade profissional por errar

Um [OCC](https://www.occ.pt/) faz as três primeiras e tem a quarta.

## O que é autoritativo, e o que não é

| | |
|---|---|
| **Autoritativo** | [Portal das Finanças](https://info.portaldasfinancas.gov.pt) · [Diário da República](https://diariodarepublica.pt) · o vendedor, quanto à garantia contratual · [DECO](https://www.deco.proteste.pt/) e os centros de arbitragem de consumo |
| **Não autoritativo** | Este repositório |

## Limites conhecidos

Registo completo, com a direção do erro de cada um, em `assets/qr-spec.json → documented_gaps`.

- **A autenticidade não é verificada.** Os campos `Q` (hash) e `R` (n.º de certificado) são
  lidos e nunca validados. Um payload escrito à mão é indistinguível de uma leitura real.
  Isto valida ESTRUTURA e ARITMÉTICA, não que o documento seja genuíno.
- **O que foi comprado não é inferido.** O código QR não o contém. Sem classificação humana
  não são produzidos prazos de garantia — de propósito.
- **Serviços comuns estão fora do DL 84/2021** (art. 1.º) e não recebem qualquer prazo.
- **Os prazos correm da ENTREGA**, não da data da fatura. Se só a data da fatura for
  conhecida, o resultado di-lo explicitamente.
- **Estado do documento `F`/`S`/`R`**: a consequência para a dedução não foi estabelecida a
  partir de fonte primária. São sinalizados e nunca tratados como dedutíveis — subvaloriza
  em vez de sobrevalorizar.
- **Faturas empresariais são recusadas**, não tratadas mal.

## Responsabilidade

Não é aceite qualquer responsabilidade por imposto liquidado, coimas aplicadas, deduções
perdidas, garantias caducadas ou decisões tomadas com base nos resultados deste software.
Ver [LICENSE](LICENSE) — o software é fornecido "como está", sem garantia de qualquer tipo.

---

## English summary

This software performs an **automated reading** of documents from public specifications and
public law. It is **not tax, legal, accounting or financial advice** and creates no
professional relationship.

**Every extracted figure must be verified by a contabilista certificado (OCC) before you
file, sign or pay anything. Every guarantee deadline must be verified with the seller, DECO
or a lawyer before you make a claim.**

Only the Autoridade Tributária and the Diário da República are authoritative. Document
authenticity is never verified; what was purchased is never inferred; ordinary services are
outside DL 84/2021 and receive no guarantee dates. No liability is accepted for tax
assessed, penalties incurred, deductions lost, guarantees expired, or decisions taken.

---

*Ferramentas gratuitas e guias em português simples: [mowei.pt](https://mowei.pt)*
