# PDF Editor Web App

Aplicação web em Flask para editar PDFs diretamente no browser, com suporte a sobreposição de texto e imagem, pré-visualização em tempo real e exportação para PDF final.

## Visão geral

- Upload de PDF e edição visual na página.
- Inserção de texto com múltiplas fontes, estilos por linha e auto-ajuste.
- Inserção de imagens com escala, recorte, movimento e filtros.
- Exportação para PDF com as alterações aplicadas.
- Exportação/importação de cópia editável (`.edits.json`) para continuar a edição depois.

## Funcionalidades presentes

### Texto

- Seleção de zona para texto.
- Campo de texto livre e opção de dividir em linhas.
- Edição por linha (texto, fonte, tamanho, cor por linha).
- Fontes padrão (Arial, Times, Georgia, Courier, etc.).
- Fontes personalizadas Noticias/ClanOT (carregadas do frontend e embebidas no PDF quando disponíveis).
- Fontes JN Helvetica (mapeadas para ficheiros `.PFB` no backend para exportação).
- Cor de fundo da caixa de texto.
- Entre-linhas configurável.
- Auto-ajustar texto à caixa.
- Centrar texto horizontalmente.
- Reedição de texto já aplicado.

### Imagem

- Seleção de zona para imagem.
- Escolha de imagem local.
- Escala de imagem de 20% a 800%.
- Ajustes de posição e recorte com handles no overlay.
- Filtros: nenhum, preto e branco, sépia, sépia + magenta.
- Intensidade do filtro.
- Reedição de imagem já aplicada.
- Apagar imagem aplicada.

### Navegação e interface

- Zoom da visualização de 50% a 800%.
- Pan horizontal e vertical.
- Botão de regresso ao menu de seleção no rodapé.
- Overlay de edição contextual sobre a área selecionada.

### Guardar e exportar

- Botão **Salvar** gera PDF final no servidor (`edited/`).
- Nome personalizado para o PDF de saída.
- Download do PDF por blob (força download, sem abrir automaticamente noutra aba).
- Geração de cópia editável `.edits.json` ao guardar.
- Importação manual de cópia editável para retomar trabalho.
- Rota para reabrir PDF já editado com projeto associado: `/edit-saved/<nome-do-pdf>`.

## Requisitos

- Python 3.8+
- `pip`

Dependências Python (em `requirements.txt`):

- Flask
- PyMuPDF
- Pillow
- gunicorn

## Instalação

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Execução

```powershell
python app.py
```

Abrir no browser:

```text
http://127.0.0.1:5000/
```

## Passo a passo de utilização

1. Abrir a aplicação e fazer upload de um PDF.
2. Escolher o separador **Texto** ou **Imagem**.
3. Clicar em **Selecionar** (ou **Selecionar zona de imagem**) e desenhar a área no documento.
4. Se for texto:
	- Escrever o conteúdo.
	- Escolher fonte, tamanho, entre-linhas e fundo.
	- Opcionalmente ativar **Auto-ajustar texto à caixa**.
	- Opcionalmente usar **Dividir texto em linhas** para personalizar linha a linha.
	- Clicar em **Aplicar texto**.
5. Se for imagem:
	- Clicar em **Escolher imagem**.
	- Ajustar escala, recorte, posição e filtro.
	- Clicar em **Aplicar imagem**.
6. Para editar novamente, usar **Editar texto aplicado** ou **Editar imagem aplicada**.
7. Definir (opcionalmente) o nome no campo de saída PDF.
8. Clicar em **Salvar**.
9. Fazer download do PDF no link **Download PDF**.
10. Se quiser continuar a edição depois:
	- Guardar o ficheiro `.edits.json` gerado automaticamente.
	- Mais tarde, carregar esse ficheiro em **Carregar cópia editável**.

## Estrutura de pastas

- `uploads/`: PDFs enviados originalmente.
- `edited/`: PDFs finais e ficheiros `.edits.json`.
- `static/fonts/news_clan/`: fontes Noticias/ClanOT.
- `static/fonts/helv_jn/`: fontes JN Helvetica (`.PFB`).

## Limitações atuais

- A edição/aplicação é feita na primeira página do PDF.
- O projeto depende da disponibilidade dos ficheiros de fontes personalizados para manter fidelidade total na exportação.

## Rotas principais

- `GET /`: página de upload.
- `POST /`: upload do PDF.
- `GET /edit/<filename>`: abrir editor para PDF enviado.
- `GET /edit-saved/<filename>`: reabrir PDF editado (e projeto, se existir).
- `POST /save`: gerar PDF editado.
- `GET /uploads/<filename>`: servir ficheiros originais.
- `GET /edited/<filename>`: servir ficheiros editados/projeto.
