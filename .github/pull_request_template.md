## Summary

Describe the user-visible problem and the focused change made here.

## Change Type

- [ ] Bug fix
- [ ] Compatibility improvement
- [ ] Documentation
- [ ] Tests or CI
- [ ] Refactor with no intended behavior change

## Verification

List the exact offline commands and results.

```powershell
python -m unittest discover -s tests -v
python -m py_compile .\scripts\image_api.py .\scripts\image_batch.py .\scripts\quality_log.py
```

## Safety Review

- [ ] No API key, token, private image, or client artifact is included.
- [ ] Tests do not make network requests or incur provider charges.
- [ ] Dry-run, overwrite protection, and explicit-request behavior remain intact.
- [ ] Any manual live-provider check is described with its request count and result.
- [ ] The five README files remain aligned where behavior changed.

## Compatibility

Note CLI, metadata, batch-manifest, provider, or documentation compatibility
impact. Write `None` when no compatibility impact is expected.
