# ILSP Krikri access, license and native-format feasibility

The one candidate is the publisher’s **Llama-Krikri-8B-Instruct Q4_K_M GGUF**. Both official repositories are public and ungated in unauthenticated Hugging Face metadata. The file is 5,041,147,264 bytes, with published LFS SHA256 `e3f93427fe0fcc016e31ed4bfbc1d10916fb97f6b2b3298445196490d315376f`, at immutable revision `3c1ce101a3e0d783a0f2223f212ccc35b4657532`. No weight bytes were downloaded.

## Access and license

[Official model card](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-GGUF/blob/3c1ce101a3e0d783a0f2223f212ccc35b4657532/README.md) identifies the **Llama 3.1 Community License**, a custom license. It permits use and distribution subject to agreement-copy, attribution/display, acceptable-use and other conditions. Its commercial threshold and derivative-model naming provisions remain applicable. The repository does not include a separate LICENSE file; the [upstream agreement](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/LICENSE) and [use policy](https://github.com/meta-llama/llama-models/blob/main/models/llama3_1/USE_POLICY.md) were saved and hashed. Public download availability does not establish unrestricted licensing.

## Revision provenance

Current base revision `5b6f2625e9b329ec70ab8cb6cbea7a06629b431f` differs from its October 2025 state only in README.md. All four published weight identities and the tokenizer/config/generation/index objects also match the February 9 model upload that predates the official Q4 upload. The Q4 object is unchanged since its February 14 first upload. This comparison uses complete published object identities, not commit titles; quantization itself was not reproduced. See `revision-template-comparison.json` and its retained API responses.

## Native format and setup caveats

The official file is a Llama-architecture GGUF. Its repository-level API reports a native Llama 3.1 Jinja template identical to the [base tokenizer configuration](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct/resolve/5b6f2625e9b329ec70ab8cb6cbea7a06629b431f/tokenizer_config.json); template SHA256 is `e10ca381b1ccc5cf9db52e371f3b6651576caee0a630b452e2816b2d404d4b65`. That API’s reported file size corresponds to Q3, so the selected Q4’s embedded template still needs verification during any separately authorized import.

The official [params](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-GGUF/resolve/3c1ce101a3e0d783a0f2223f212ccc35b4657532/params) default to **131072 context**, temperature 0.5 and top-p 0.95; [system](https://huggingface.co/ilsp/Llama-Krikri-8B-Instruct-GGUF/resolve/3c1ce101a3e0d783a0f2223f212ccc35b4657532/system) supplies a Greek assistant persona. Any future production-request comparison must explicitly bind the intended 4096 context, temperature 0, native stop/template behavior and actual system/user rendering before generation. Inheriting the publisher’s large context would violate the intended modest-resource setup.

A 5.04 GB file alone does not prove a process fits 6 GiB or runs fast enough on four CPUs. No runtime or quality result is claimed, and no download, cleanup, inference or production integration is authorized by this metadata record.
