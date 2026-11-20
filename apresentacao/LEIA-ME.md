# Kit de apresentação

Permite que outra pessoa instale o app pelo QR Code e use o backend rodando no
notebook, sem cabo e sem internet entre o celular e o notebook.

```text
celular ──Wi-Fi (Hotspot móvel do notebook)──> notebook 192.168.137.1
                                                 ├─ :8080  download do APK
                                                 └─ :8000  backend NutriIA
```

## Antes (uma vez, no notebook)

1. Projeto instalado e funcionando, conforme o `COMO_RODAR.md` (PostgreSQL,
   `.env`, `.venv`, migrações).
2. O APK em `apresentacao/publico/NutriIA.apk`:
   - com Android Studio no notebook: `powershell -ExecutionPolicy Bypass -File apresentacao\gerar-apk.ps1`;
   - sem Android Studio: copie o `NutriIA.apk` gerado em outra máquina para
     essa pasta (o mesmo APK serve para qualquer notebook).
3. O notebook precisa de internet (Wi-Fi ou cabo): o backend consulta o Open
   Food Facts. A maioria dos notebooks consegue usar o Wi-Fi e compartilhar o
   hotspot ao mesmo tempo.

## Na hora

1. Clique duas vezes em `apresentacao\iniciar.bat`. Ele:
   - libera as portas 8000 e 8080 no firewall, só para a rede do hotspot
     (pede permissão de administrador na primeira vez);
   - abre a tela do **Hotspot móvel** se ele estiver desligado;
   - sobe o backend e o download do APK;
   - abre a página com os dois QR Codes.
2. Mostre a página: o QR **1** conecta o celular no Wi-Fi do notebook e o QR
   **2** baixa o app.
3. No celular: instalar, permitir "apps desta fonte" se o Android pedir, criar
   uma conta e escanear um produto.

Para encerrar, feche as janelas "NutriIA backend" e "NutriIA download do APK".

## Bom saber

- Funciona só em Android (APK).
- O endereço `192.168.137.1` é o padrão do Hotspot móvel do Windows; por isso o
  mesmo APK funciona em qualquer notebook.
- Foto do rótulo só funciona com `GEMINI_API_KEY` no `.env`.
