# Rights and licences

This page states what we checked. It is not legal advice.

## The parts and their licences

| Part | Licence | Included here? |
|---|---|---|
| score-to-song (this code, docs, example scores) | Apache License 2.0 ([LICENSE](../LICENSE)) | yes |
| mlx-Yue (MLX port of YuE2) | Apache License 2.0 | no: cloned by `scripts/install.sh` |
| YuE2 weights (`m-a-p/YuE2-3B`, `m-a-p/YuE2-Vae`) | CC BY-NC 4.0 + additional permission, see below | no: downloaded and converted on your machine |
| audio-separator | MIT | no: installed from PyPI |
| BS-RoFormer weights `model_bs_roformer_ep_317_sdr_12.9755` | not stated by the distributor as far as we found; we have not verified it | no: downloaded by audio-separator |

## YuE2 weights and what you generate

The [YuE2 model licence](https://github.com/multimodal-art-projection/YuE/blob/main/MODEL_LICENSE)
(read 2026-10-25) covers YuE2-3B, YuE2-Vae and YuE2-Vae-legacy. In short:

- The weights are under **Creative Commons Attribution-NonCommercial 4.0**.
- An **additional permission dated 2026-09-16** lets *personal users, content creators and musicians
  acting individually* use the weights free of charge to generate outputs, and **publish, distribute,
  sell, license or otherwise monetise those outputs**, without a separate licence or royalties.
- It **does not authorise commercial use of the weights by companies**: they must ask the authors for a
  commercial licence.
- It does not cover redistributing or selling the weights, nor the rights on third-party material in
  your inputs or outputs. Crediting YuE2 is encouraged, not required, for generated works.

So before you release music made with this toolkit, check whether you act as an individual creator or
for a company, and read the licence itself.

## Your inputs

A model's licence does not settle the rights on what you give it. The toolkit only sends the model your
score, your style text and your lyrics. Keep them yours:

- write original melodies; do not transcribe or closely imitate an existing recording;
- do not put names of artists, titles or recordings in the style or the lyrics;
- studying a reference recording on your own machine is a different act from using it as an input or
  shipping something derived from it. score-to-song has no command that feeds audio into the model.

## Separated voices

`separate` produces **estimates** of a voice from a mixed render. They contain residue of the
accompaniment and are not the model's own stems. If you deliver stems built from them, say so.

## Contributions

By contributing you agree that your contribution is licensed under the Apache License 2.0 (section 5 of
the licence). Do not contribute audio, weights, or material you do not have the right to share.
