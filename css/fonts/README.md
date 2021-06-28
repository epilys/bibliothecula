# Compressing `woff2`

https://fonttools.readthedocs.io/en/latest/subset/index.html

```shell
pyftsubset css/fonts/Amstelvar-Roman-VF-full.woff2 --text-file=index.html --flavor=woff2
mv css/fonts/Amstelvar-Roman-VF-full.subset.woff2 css/fonts/Amstelvar-Roman-VF.woff2
```
