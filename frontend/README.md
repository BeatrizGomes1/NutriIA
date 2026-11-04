# Frontend

Aplicativo Android do NutriIA, em Kotlin com Android Views (XML) e ViewBinding.

Para rodar junto com o backend, siga o [guia COMO_RODAR.md](../COMO_RODAR.md).

## Organização

```text
app/src/main/java/com/uece/nutriia/
├── data/
│   ├── local/        # sessão (token JWT) em SharedPreferences
│   ├── model/        # data classes enviadas e recebidas pela API
│   ├── remote/       # Retrofit: rotas, cliente HTTP e tratamento de erros
│   └── repository/   # acesso aos dados usado pelas telas
└── ui/               # uma pasta por tela (Activities, adapters e helpers)
```

- As Activities cuidam da interface e chamam os repositories com coroutines
  (`lifecycleScope`).
- A leitura de código de barras usa CameraX + ML Kit (`ui/escanear/LeitorCodigoBarras.kt`).
- O endereço do backend vem de `BuildConfig.API_BASE_URL`
  (padrão `http://10.0.2.2:8000/api/v1/`; pode ser trocado pela propriedade
  `nutriia.apiBaseUrl`, ver o guia).

O backend não deve depender diretamente de arquivos ou módulos desta pasta.
