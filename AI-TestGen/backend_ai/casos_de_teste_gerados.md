## Particionamento de Equivalência para Estória de Usuário: Login no Sistema

### 1. Variáveis e Classes de Equivalência

**Variável 1: Usuário**

*   **Nome:** Usuário (Login)
*   **Descrição:** Identificador único do usuário no sistema.
*   **Classes de Equivalência:**
    *   **Válida - Tamanho Mínimo:** Usuário com 5 caracteres alfanuméricos.
    *   **Válida - Tamanho Máximo:** Usuário com 15 caracteres alfanuméricos.
    *   **Válida - Tamanho Intermediário:** Usuário com tamanho entre 6 e 14 caracteres alfanuméricos.
    *   **Inválida - Tamanho Mínimo:** Usuário com menos de 5 caracteres.
    *   **Inválida - Tamanho Máximo:** Usuário com mais de 15 caracteres.
    *   **Inválida - Caracteres Especiais:** Usuário contendo caracteres especiais.
    *   **Inválida - Vazio:** Usuário não informado.

**Variável 2: Senha**

*   **Nome:** Senha
*   **Descrição:** Credencial de acesso do usuário.
*   **Classes de Equivalência:**
    *   **Válida - Completa:** Senha com 8-15 caracteres, contendo pelo menos 1 letra maiúscula, 1 letra minúscula, 1 número e 1 caractere especial.
    *   **Válida - Tamanho Mínimo:** Senha com 8 caracteres, contendo pelo menos 1 letra maiúscula, 1 letra minúscula, 1 número e 1 caractere especial.
    *   **Válida - Tamanho Máximo:** Senha com 15 caracteres, contendo pelo menos 1 letra maiúscula, 1 letra minúscula, 1 número e 1 caractere especial.
    *   **Inválida - Tamanho Mínimo:** Senha com menos de 8 caracteres.
    *   **Inválida - Tamanho Máximo:** Senha com mais de 15 caracteres.
    *   **Inválida - Sem Maiúscula:** Senha sem pelo menos uma letra maiúscula.
    *   **Inválida - Sem Minúscula:** Senha sem pelo menos uma letra minúscula.
    *   **Inválida - Sem Número:** Senha sem pelo menos um número.
    *   **Inválida - Sem Caractere Especial:** Senha sem pelo menos um caractere especial.
    *   **Inválida - Vazia:** Senha não informada.

**Variável 3: Status da Conta**

*   **Nome:** Status da Conta
*   **Descrição:** Indica se a conta do usuário está ativa ou bloqueada.
*   **Classes de Equivalência:**
    *   **Válida - Ativa:** Conta do usuário ativa.
    *   **Inválida - Bloqueada:** Conta do usuário bloqueada.

### 2. Casos de Teste Sugeridos

| ID   | Descrição                               | Condições                                                              | Dados de Entrada                               | Resultado Esperado                                                              |
| :--- | :-------------------------------------- | :--------------------------------------------------------------------- | :--------------------------------------------- | :------------------------------------------------------------------------------ |
| CT01 | Login com usuário e senha válidos (ativa) | Usuário e senha atendem aos critérios de validação, conta ativa.      | Usuário: "Teste123", Senha: "Teste123!", Status: Ativa | Login bem-sucedido, redirecionamento para a área restrita.                     |
| CT02 | Login com usuário válido, senha inválida | Usuário válido, senha não atende aos critérios de validação.           | Usuário: "Teste123", Senha: "teste", Status: Ativa | Mensagem de erro indicando senha inválida.                                     |
| CT03 | Login com usuário inválido, senha válida | Usuário não atende aos critérios de validação, senha válida.           | Usuário: "Tes", Senha: "Teste123!", Status: Ativa | Mensagem de erro indicando usuário inválido.                                   |
| CT04 | Login com usuário e senha inválidos      | Usuário e senha não atendem aos critérios de validação.               | Usuário: "Te", Senha: "teste", Status: Ativa | Mensagens de erro indicando usuário e senha inválidos.                         |
| CT05 | Login com conta bloqueada                | Usuário e senha válidos, conta bloqueada.                              | Usuário: "Teste123", Senha: "Teste123!", Status: Bloqueada | Mensagem de erro indicando que a conta está bloqueada.                         |
| CT06 | Login com usuário tamanho mínimo válido   | Usuário com 5 caracteres alfanuméricos, senha válida.                | Usuário: "abcde", Senha: "Teste123!", Status: Ativa | Login bem-sucedido.                                                             |
| CT07 | Login com usuário tamanho máximo válido   | Usuário com 15 caracteres alfanuméricos, senha válida.               | Usuário: "abcdefghijklmno", Senha: "Teste123!", Status: Ativa | Login bem-sucedido.                                                             |
| CT08 | Login com usuário tamanho mínimo inválido | Usuário com 4 caracteres, senha válida.                               | Usuário: "abcd", Senha: "Teste123!", Status: Ativa | Mensagem de erro indicando usuário inválido (tamanho).                         |
| CT09 | Login com usuário tamanho máximo inválido | Usuário com 16 caracteres, senha válida.                              | Usuário: "abcdefghijklmnop", Senha: "Teste123!", Status: Ativa | Mensagem de erro indicando usuário inválido (tamanho).                         |
| CT10 | Login com usuário com caractere especial | Usuário contendo um caractere especial, senha válida.                | Usuário: "Teste@123", Senha: "Teste123!", Status: Ativa | Mensagem de erro indicando usuário inválido (caracteres especiais).           |
| CT11 | Login com senha tamanho mínimo válido     | Usuário válido, senha com 8 caracteres, atendendo aos requisitos.     | Usuário: "Teste123", Senha: "Ab1!", Status: Ativa | Login bem-sucedido.                                                             |
| CT12 | Login com senha tamanho máximo válido     | Usuário válido, senha com 15 caracteres, atendendo aos requisitos.    | Usuário: "Teste123", Senha: "Abcdefgh123!@#", Status: Ativa | Login bem-sucedido.                                                             |
| CT13 | Login com senha tamanho mínimo inválido   | Usuário válido, senha com 7 caracteres.                               | Usuário: "Teste123", Senha: "Abc1!", Status: Ativa | Mensagem de erro indicando senha inválida (tamanho).                         |
| CT14 | Login com senha tamanho máximo inválido   | Usuário válido, senha com 16 caracteres.                              | Usuário: "Teste123", Senha: "Abcdefgh123!@#$", Status: Ativa | Mensagem de erro indicando senha inválida (tamanho).                         |
| CT15 | Login com senha sem letra maiúscula      | Usuário válido, senha sem letra maiúscula.                             | Usuário: "Teste123", Senha: "abc1!", Status: Ativa | Mensagem de erro indicando senha inválida (sem maiúscula).                    |
| CT16 | Login com senha sem letra minúscula      | Usuário válido, senha sem letra minúscula.                             | Usuário: "Teste123", Senha: "ABC1!", Status: Ativa | Mensagem de erro indicando senha inválida (sem minúscula).                    |
| CT17 | Login com senha sem número               | Usuário válido, senha sem número.                                     | Usuário: "Teste123", Senha: "Abc!", Status: Ativa | Mensagem de erro indicando senha inválida (sem número).                       |
| CT18 | Login com senha sem caractere especial   | Usuário válido, senha sem caractere especial.                          | Usuário: "Teste123", Senha: "Abc1", Status: Ativa | Mensagem de erro indicando senha inválida (sem caractere especial).           |
| CT19 | Login com usuário e senha vazios         | Usuário e senha não informados.                                       | Usuário: "", Senha: "", Status: Ativa | Mensagens de erro indicando usuário e senha obrigatórios.                      |