# PDF Editor Web App

Esta aplicação demonstra uma interface web simples para carregar um ficheiro PDF e colocar imagens ou texto na primeira página.

## Requisitos

- Python 3.8+
- `pip` instalado

## Instalação

```bash
python -m venv venv
venv\Scripts\activate    # Windows
pip install -r requirements.txt
```

## Execução

```bash
python app.py
```

Ao abrir `http://127.0.0.1:5000/` poderá carregar um PDF (apenas PDF aceites). Após o upload será levado à interface de edição.

## Funcionalidades básicas

- Seleccionar área na página com o botão "Selecionar" em texto ou imagem
- Para imagem, após seleccionar permite fazer upload de uma imagem que será desenhada na área
- Para texto, permite inserir texto com escolha de fonte e tamanho
- Após colocar texto ou imagem, é possível clicar novamente nessa região para reabrir o painel e **editar** o conteúdo ou **excluir** o elemento
- Após editar, botão **Salvar** gera um ficheiro PDF com as alterações incorporadas (e também um PNG como etapa intermédia)

> Esta é uma primeira versão protótipo. Mais recursos como suporte a múltiplas páginas, guardando o resultado, etc. podem ser adicionados.
