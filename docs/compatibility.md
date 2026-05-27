# Compatibility

This table lists known vacuum models and their support for the REST and MQTT transports.
Visit a model's details page to see the full feature-level compatibility matrix for that model.

> **Adding a new model?**
> The goal is to identify both supported and known unsupported models. This allows us to track and add new mappings targeted at specific models. Please open a PR with the following changes to contribute to this list.
>
> 1. Create `/docs/compatibility/{model}.md` using the template in [`/docs/compatibility/template.md`](/docs/compatibility/template.md) as a reference.
> 2. Add a row to the table above with the model, transport support, and a link to the new file.
>
>Hint: You can [use the CLI](/docs/cli.md#Compatibility-Testing) to generate this automatically.


| Model        | REST | MQTT | Details                                |
| ------------ | :--: | :--: | -------------------------------------- |
| `RV2310CGUS` |  ❌  |  ✅  | [Details](/docs/compatibility/rv2310cgus.md) |
| `RV1001AEC`  |  ❌  |  ❌  | [Details](/docs/compatibility/rv1001aec.md)  |
| `RV2610BFCA` |  ❌  |  ✅  | [Details](/docs/compatibility/rv2610bfca.md) |
| `UR2500SR`   |  ❌  |  ✅  | [Details](/docs/compatibility/ur2500sr.md)   |
| `RV2001DRUS` |  ✅  |  ❌  | [Details](/docs/compatibility/rv2001drus.md)   |
| `RV1100ARUS` |  ❌  |  ✅  | [Details](/docs/compatibility/RV1100ARUS_AV1110ARUS.md) |
| `UR2360EEUS` |  ❌  |  ❌  | [Details](/docs/compatibility/UR2360EEUS.md) |
