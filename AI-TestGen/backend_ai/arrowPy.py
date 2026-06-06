import json
from datasets import Dataset

# Lê o arquivo
dataset = Dataset.from_file("data-00000-of-00001.arrow")
df = dataset.to_pandas()

todas_estorias = []

print(f"Iniciando a extração de {len(df)} registros...")

# Percorre TODAS as linhas do DataFrame
for index, row in df.iterrows():
    try:
        # Converte as strings JSON para dicionários/listas Python
        usecase_dict = json.loads(row['usecase'])
        testcases_lista = json.loads(row['testcases'])
        
        # Extrai os nomes dos casos de teste
        nomes_casos_teste = [tc['name'] for tc in testcases_lista if 'name' in tc]
        
        # Monta um objeto estruturado
        estoria_completa = {
            "id": index + 1,
            "estoria": usecase_dict.get('name', 'Sem nome'),
            "descricao": usecase_dict.get('description', ''),
            "quantidade_casos_teste": len(nomes_casos_teste),
            "casos_de_teste": nomes_casos_teste
        }
        todas_estorias.append(estoria_completa)
        
    except Exception as e:
        print(f"Erro ao processar a linha {index}: {e}")

# Salva tudo em um arquivo JSON
arquivo_saida = "dataset_extraido.json"
with open(arquivo_saida, "w", encoding="utf-8") as f:
    json.dump(todas_estorias, f, ensure_ascii=False, indent=4)

print(f"Extração concluída com sucesso!")
print(f"Todos os dados foram salvos no arquivo: {arquivo_saida}")