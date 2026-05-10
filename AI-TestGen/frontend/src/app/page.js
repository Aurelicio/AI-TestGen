"use client";
import { useState } from "react";

export default function Home() {
  const [estoria, setEstoria] = useState("");
  const [dados, setDados] = useState(null);
  const [loading, setLoading] = useState(false);
  const [visaoAtiva, setVisaoAtiva] = useState("detalhada");
  const [isAnimating, setIsAnimating] = useState(false);
  const [progresso, setProgresso] = useState(null);
  const [etapaAtiva, setEtapaAtiva] = useState(null);
  const [temEtapas, setTemEtapas] = useState(false); // Controla se mostra o bloco de etapas

  const mudarVisao = (novaVisao) => {
    if (novaVisao === visaoAtiva) return;

    setIsAnimating(true); // Esconde a tela atual
    setTimeout(() => {
      setVisaoAtiva(novaVisao); // Troca o conteúdo no "escuro"
      setIsAnimating(false); // Mostra a nova tela
    }, 250); // 250 milissegundos de transição
  };

  const gerarTestes = async () => {
    // --- PRÉ-VALIDAÇÃO LOCAL (FAIL-FAST) ---
    if (!estoria.trim()) return;

    const regexTitulo = /t[íi]tulo/i;
    const regexStakeholder = /como um/i;

    if (!regexTitulo.test(estoria) || !regexStakeholder.test(estoria)) {
      setDados({
        casos_de_teste: [],
        erro_validacao:
          "Atenção: A estória deve conter explicitamente as palavras 'Título', que define o título da estória e 'Como um' que indica claramente o stakeholder para iniciar a análise da IA." +
          "" +
          "\n\nTemplate esperado:" +
          "\n\n**Título:** [Descreva a funcionalidade de forma concisa]" +
          "\n**Como um** [tipo de usuário]," +
          "\n**Eu quero** [objetivo]," +
          "\n**Para que** [benefício]." +
          "\n**Detalhamento:** [Informações adicionais]" +
          "\n**Critérios de Aceitação:**" +
          "\n- Regra 1: [Com limite numérico ou tamanho mensurável]" +
          "\n- Regra 2: [Com limite numérico ou tamanho mensurável]" +
          "\n...",
      });
      return;
    }

    setLoading(true);
    setDados(null);
    setProgresso(null);
    setEtapaAtiva(null);
    setTemEtapas(false); // Reset quando começa o loading

    try {
      const eventSource = new EventSource(
        `http://localhost:8000/api/generate-tests-stream?estoria=${encodeURIComponent(estoria)}`,
      );

      // Cria um FormData para enviar como POST
      const formData = new FormData();
      formData.append("estoria", estoria);

      // Fecha a conexão anterior se existir
      eventSource.close();

      // Faz a requisição POST como stream usando fetch com modo manual
      const response = await fetch(
        "http://localhost:8000/api/generate-tests-stream",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ estoria }),
        },
      );

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const linhas = chunk.split("\n");

        for (const linha of linhas) {
          if (linha.startsWith("data: ")) {
            const jsonStr = linha.slice(6);
            if (jsonStr.trim()) {
              try {
                const evento = JSON.parse(jsonStr);
                processarEvento(evento);
              } catch (e) {
                console.error("Erro ao parsear JSON:", e);
              }
            }
          }
        }
      }
    } catch (error) {
      console.error("Erro na conexão:", error);
      setDados({
        casos_de_teste: [],
        erro_validacao: "Erro ao conectar com o servidor.",
      });
    } finally {
      setLoading(false);
    }
  };

  const processarEvento = (evento) => {
    const { tipo } = evento;

    if (tipo === "etapa_inicio") {
      setTemEtapas(true); // Mostra o bloco de etapas quando recebe primeiro evento de etapa
      setEtapaAtiva({
        numero: evento.etapa,
        titulo: evento.titulo,
        descricao: evento.descricao,
      });
      // O percentual inicial já vem no evento
      setProgresso({ etapa: evento.etapa, percentual: evento.percentual || 0 });
    } else if (tipo === "etapa_resultado") {
      // Atualiza com o percentual correto que vem no evento
      setProgresso({ etapa: evento.etapa, percentual: evento.percentual || 0 });
    } else if (tipo === "completo") {
      setDados(evento.dados);
      setProgresso({ etapa: 4, percentual: 100 });
      setEtapaAtiva(null);
    } else if (tipo === "erro" || tipo === "validacao_falhou") {
      setDados({
        casos_de_teste: [],
        erro_validacao: evento.mensagem,
      });
      setProgresso(null);
      setEtapaAtiva(null);
    }
  };

  const limparResultados = () => {
    setDados(null);
    setEstoria("");
  };

  return (
    <div className="min-h-screen bg-[#f8fafc] font-sans text-slate-900">
      <nav className="bg-white border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-[1600px] mx-auto px-6 h-16 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 bg-indigo-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold">A</span>
            </div>
            <h1 className="text-xl font-extrabold tracking-tight text-slate-800">
              AI-TestGen{" "}
              <span className="text-indigo-600 font-medium text-sm">
                Dashboard
              </span>
            </h1>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={limparResultados}
              disabled={!dados || dados.casos_de_teste?.length === 0}
              className="bg-rose-50 text-rose-700 hover:bg-rose-100 px-4 py-2 rounded-lg text-sm font-bold transition-all border border-rose-100 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-rose-50"
            >
              <svg
                className="w-8 h-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                />
              </svg>
              Limpar
            </button>

            <button
              disabled={!dados || dados.casos_de_teste?.length === 0}
              className="bg-indigo-50 text-indigo-700 hover:bg-indigo-100 px-4 py-2 rounded-lg text-sm font-bold transition-all border border-indigo-100 flex items-center gap-2 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:bg-indigo-50"
            >
              <svg
                className="w-8 h-8"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"
                />
              </svg>
              Exportar Resultados
            </button>
          </div>
        </div>
      </nav>

      <main className="p-8 max-w-[1600px] mx-auto space-y-8">
        {/* Card de Entrada de Dados */}
        <section className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="p-6 div-requisitos-sistema">
            <div className="flex items-center gap-2 mb-4 text-slate-500">
              <svg
                className="w-7 h-7"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth="2"
                  d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                />
              </svg>
              <h3 className="font-semibold uppercase tracking-wider text-xs">
                Requisitos do Sistema
              </h3>
            </div>
            <textarea
              className="input-estoria-usuario w-full p-4     bg-slate-50 border border-slate-200 rounded-x focus:ring-4 focus:ring-indigo-500/10 focus:border-indigo-500 outline-none h-40 text-slate-700 transition-all resize-none"
              placeholder="Descreva a Estória de Usuário no formato: Título da Estória (Título...), Stakeholder (Como um...), Problema (Eu quero...), Benefício (Para...), Detalhamento e Critérios de Aceitação (Regras de validação).
              Exemplo: Título da Estória: Criar conta no Sistema. Como um usuário eu quero criar uma conta no sistema para que seja realizado o login e visualizadas as funções disponíveis. Detalhamento: Deve ser informado um usuário e uma senha. O usuário pode conter caracteres alfanuméricos, mas não caracteres especiais, com um tamanho mínimo de 5 caracteres, e um máximo de 15 caracteres. 
A senha precisa conter obrigatoriamente no mímino 8 caracteres e no máximo 15, deve conter no mínimo 1 letra maiúscula, no mínimo 1 letra minúscula, 
no mínimo 1 número e no mínimo 1 caractere especial."
              value={estoria}
              onChange={(e) => setEstoria(e.target.value)}
            />
            <div className="mt-4 flex justify-end">
              <button
                onClick={gerarTestes}
                disabled={loading || !estoria.trim()}
                className="bg-indigo-600 hover:bg-indigo-700 text-white px-8 py-3 rounded-xl font-bold disabled:bg-slate-300 transition-all shadow-lg shadow-indigo-200 flex items-center gap-3"
              >
                {loading && (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></div>
                )}
                {loading ? "Processando..." : "Gerar Casos de Teste"}
              </button>
            </div>
          </div>
        </section>

        {/* Bloco de Progresso das Etapas - SÓ APARECE COM PROMPT CHAINING */}
        {loading && temEtapas && (
          <div className="bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-2xl p-8 shadow-lg">
            <div className="space-y-6">
              {/* Título e descrição */}
              <div>
                <div className="flex items-center gap-3 mb-2">
                  <div className="w-2 h-2 bg-indigo-600 rounded-full animate-pulse"></div>
                  <h3 className="font-bold text-indigo-900 text-lg">
                    Processando estória do usuário...
                  </h3>
                </div>
                {etapaAtiva && (
                  <div className="ml-5">
                    <p className="text-indigo-700 font-semibold text-sm">
                      {etapaAtiva.titulo}
                    </p>
                    <p className="text-indigo-600 text-xs mt-1">
                      {etapaAtiva.descricao}
                    </p>
                  </div>
                )}
              </div>

              {/* Barra de progresso */}
              {progresso && (
                <div>
                  <div className="flex justify-between items-center mb-2">
                    <span className="text-xs font-bold text-indigo-700 uppercase tracking-wider">
                      Etapa {progresso.etapa} de 4
                    </span>
                    <span className="text-xs font-bold text-indigo-600">
                      {progresso.percentual}%
                    </span>
                  </div>
                  <div className="w-full bg-white rounded-full h-2.5 border border-indigo-200 overflow-hidden shadow-inner">
                    <div
                      className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${progresso.percentual}%` }}
                    ></div>
                  </div>
                </div>
              )}

              {/* Timeline das 4 etapas */}
              <div className="space-y-3 pt-2">
                {/* Etapa 1: Validação da Estrutura */}
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                      progresso?.etapa >= 1
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "border-slate-300 text-slate-400"
                    }`}
                  >
                    {progresso?.etapa > 1 ? (
                      <svg
                        className="w-3 h-3"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      <span className="text-xs font-bold">1</span>
                    )}
                  </div>
                  <div className="pt-0.5">
                    <p className="text-sm font-bold text-slate-800">
                      Validação da Estrutura
                    </p>
                    <p className="text-xs text-slate-500">
                      Verificando componentes obrigatórios
                    </p>
                  </div>
                </div>

                {/* Etapa 2: Few Shot Learning */}
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                      progresso?.etapa >= 2
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "border-slate-300 text-slate-400"
                    }`}
                  >
                    {progresso?.etapa > 2 ? (
                      <svg
                        className="w-3 h-3"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      <span className="text-xs font-bold">2</span>
                    )}
                  </div>
                  <div className="pt-0.5">
                    <p className="text-sm font-bold text-slate-800">
                      Treinamento com Exemplos (Few Shot)
                    </p>
                    <p className="text-xs text-slate-500">
                      Aplicando Particionamento de Equivalência e Análise de
                      Valor Limite
                    </p>
                  </div>
                </div>

                {/* Etapa 3: Identificação de Classes */}
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                      progresso?.etapa >= 3
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "border-slate-300 text-slate-400"
                    }`}
                  >
                    {progresso?.etapa > 3 ? (
                      <svg
                        className="w-3 h-3"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      <span className="text-xs font-bold">3</span>
                    )}
                  </div>
                  <div className="pt-0.5">
                    <p className="text-sm font-bold text-slate-800">
                      Identificação de Classes e Regras
                    </p>
                    <p className="text-xs text-slate-500">
                      Mapeando classes válidas, inválidas e valores limites
                    </p>
                  </div>
                </div>

                {/* Etapa 4: Geração de Casos de Teste */}
                <div className="flex items-start gap-3">
                  <div
                    className={`w-6 h-6 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-all ${
                      progresso?.etapa >= 4
                        ? "bg-indigo-600 border-indigo-600 text-white"
                        : "border-slate-300 text-slate-400"
                    }`}
                  >
                    {progresso?.etapa > 4 ? (
                      <svg
                        className="w-3 h-3"
                        fill="currentColor"
                        viewBox="0 0 20 20"
                      >
                        <path
                          fillRule="evenodd"
                          d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                          clipRule="evenodd"
                        />
                      </svg>
                    ) : (
                      <span className="text-xs font-bold">4</span>
                    )}
                  </div>
                  <div className="pt-0.5">
                    <p className="text-sm font-bold text-slate-800">
                      Geração de Casos de Teste
                    </p>
                    <p className="text-xs text-slate-500">
                      Sintetizando cenários de teste com valores limites
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Bloco de Loading Simples - SEM PROMPT CHAINING */}
        {loading && !temEtapas && (
          <div className="bg-slate-50 border border-slate-200 rounded-2xl p-8 shadow-sm">
            <div className="flex items-center gap-4">
              <div className="w-6 h-6 border-3 border-indigo-200 border-t-indigo-600 rounded-full animate-spin"></div>
              <div>
                <p className="font-bold text-slate-800">
                  Gerando casos de teste...
                </p>
                <p className="text-sm text-slate-500">Processando estória</p>
              </div>
            </div>
          </div>
        )}

        {/* Bloco de Avisos e Erros do Servidor */}
        {dados &&
          (!dados.casos_de_teste || dados.casos_de_teste.length === 0) && (
            <div className="bg-amber-50 border-l-4 border-amber-500 p-6 rounded-xl mt-6 shadow-sm">
              <div className="flex items-center gap-2 text-amber-800 mb-3">
                <svg
                  className="w-8 h-8"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth="2"
                    d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                  />
                </svg>
                <p className="font-extrabold uppercase tracking-tight">
                  Status da Análise
                </p>
              </div>
              <p className="text-amber-700 font-mono text-sm whitespace-pre-wrap bg-white/50 p-4 rounded-lg border border-amber-100">
                {/* Mostra o erro de validação da IA OU o erro 500 do Python */}
                {dados.erro_validacao ||
                  dados.detail ||
                  "Falha ao processar a requisição."}
              </p>
            </div>
          )}

        {/* Bloco de Resultados (Só renderiza se tiver MAIS de 0 itens comprovadamente) */}
        {dados && dados.casos_de_teste && dados.casos_de_teste.length > 0 && (
          <div className="animate-in slide-in-from-bottom-4 duration-700">
            {/* --- MENU DE ABAS (TABS) --- */}
            <div className="flex justify-center mb-8">
              <div className="bg-slate-200/60 p-1.5 rounded-xl inline-flex gap-1 shadow-inner">
                <button
                  onClick={() => mudarVisao("detalhada")}
                  className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-all duration-300 flex items-center gap-2 ${visaoAtiva === "detalhada" ? "bg-white text-indigo-600 shadow-sm" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"
                    />
                  </svg>
                  Visão Detalhada
                </button>
                <button
                  onClick={() => mudarVisao("executiva")}
                  className={`px-6 py-2.5 rounded-lg text-sm font-bold transition-all duration-300 flex items-center gap-2 ${visaoAtiva === "executiva" ? "bg-white text-indigo-600 shadow-sm" : "text-slate-500 hover:text-slate-700 hover:bg-slate-200/50"}`}
                >
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth="2"
                      d="M4 6h16M4 10h16M4 14h16M4 18h16"
                    />
                  </svg>
                  Visão de Execução
                </button>
              </div>
            </div>

            {/* --- ÁREA DE CONTEÚDO --- */}
            {/* NOVO: A div abaixo reage ao estado 'isAnimating' fazendo um fade in/out com leve movimento */}
            <div
              className={`w-full transition-all duration-250 ease-in-out transform ${isAnimating ? "opacity-0 scale-[0.98] translate-y-2" : "opacity-100 scale-100 translate-y-0"}`}
            >
              {/* CONTEÚDO 1: VISÃO DETALHADA */}
              {visaoAtiva === "detalhada" && (
                <div className="space-y-6 max-w-8xl mx-auto">
                  <div className="flex items-center justify-between px-2">
                    <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                      <span className="w-1 h-6 bg-indigo-600 rounded-full"></span>
                      Visualização Detalhada
                    </h2>
                    <span className="text-xs font-medium text-slate-400 font-mono bg-white px-3 py-1 rounded-full border border-slate-200">
                      {dados.casos_de_teste?.length} cenários gerados
                    </span>
                  </div>

                  {/* Os cards agora ficam em um grid de 2 colunas em telas grandes */}
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                    {dados.casos_de_teste?.map((teste, index) => (
                      <div
                        key={index}
                        className="bg-white rounded-2xl border border-slate-200 hover:border-indigo-300 hover:scale-[1.04] hover:shadow-xl transition-all duration-300 group shadow-sm flex flex-col cursor-default"
                      >
                        <div className="px-5 py-4 border-b border-slate-100 flex justify-between items-center bg-slate-50/50 rounded-t-2xl">
                          <span className="font-mono font-bold text-indigo-600 text-sm">
                            {teste.id}
                          </span>
                          <span
                            className={`text-[10px] font-bold px-3 py-1 rounded-full uppercase tracking-widest ${teste.tipo === "Positivo" ? "bg-emerald-50 text-emerald-600" : "bg-rose-50 text-rose-600"}`}
                          >
                            {teste.tipo}
                          </span>
                        </div>
                        <div className="p-5 space-y-4 flex-1">
                          <p className="text-slate-800 font-bold leading-tight group-hover:text-indigo-900 transition-colors">
                            {teste.descricao}
                          </p>
                          <div className="grid grid-cols-1 gap-3">
                            <div className="bg-slate-50 p-3 rounded-xl border border-slate-100">
                              <span className="text-[10px] uppercase font-bold text-slate-400 block mb-1">
                                Dados de Entrada
                              </span>
                              <code className="text-sm text-slate-700 font-mono break-all">
                                {teste.dados_entrada}
                              </code>
                            </div>
                            <div className="bg-indigo-50/30 p-3 rounded-xl border border-indigo-50 h-full">
                              <span className="text-[10px] uppercase font-bold text-indigo-400 block mb-1">
                                Resultado Esperado
                              </span>
                              <p className="text-sm text-indigo-900 leading-relaxed font-medium">
                                {teste.resultado_esperado}
                              </p>
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* CONTEÚDO 2: VISÃO DE EXECUÇÃO */}
              {visaoAtiva === "executiva" && (
                <div className="space-y-6 max-w-8xl mx-auto">
                  <div className="flex items-center justify-between px-2">
                    <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                      <span className="w-1 h-6 bg-slate-400 rounded-full"></span>
                      Visão de Execução
                    </h2>
                    <span className="text-xs font-medium text-slate-400 font-mono bg-white px-3 py-1 rounded-full border border-slate-200">
                      Formato Tabela
                    </span>
                  </div>

                  <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full text-left">
                        <thead>
                          <tr className="bg-slate-50 text-slate-500 border-b border-slate-200">
                            <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-wider whitespace-nowrap">
                              ID
                            </th>
                            <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-wider">
                              Título do Cenário
                            </th>
                            <th className="px-6 py-4 text-[11px] font-bold uppercase tracking-wider whitespace-nowrap">
                              Tipo
                            </th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {dados.casos_de_teste?.map((teste, index) => (
                            <tr
                              key={index}
                              className="hover:bg-slate-50/80 transition-colors"
                            >
                              <td className="px-6 py-4 font-mono text-xs font-bold text-indigo-600 align-top">
                                {teste.id}
                              </td>
                              <td className="px-6 py-4 align-top">
                                <p className="text-sm text-slate-800 font-bold mb-1">
                                  {teste.descricao}
                                </p>
                                <p className="text-[11px] font-mono text-slate-500 bg-slate-100 inline-block px-2 py-0.5 rounded">
                                  {teste.classe_equivalencia}
                                </p>
                              </td>
                              <td className="px-6 py-4 align-top">
                                <div className="flex items-center gap-2 mt-0.5">
                                  <span
                                    className={`w-2.5 h-2.5 rounded-full flex-shrink-0 ${teste.tipo === "Positivo" ? "bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.4)]" : "bg-rose-500 shadow-[0_0_8px_rgba(244,63,94,0.4)]"}`}
                                  ></span>
                                  <span className="text-xs font-bold text-slate-700">
                                    {teste.tipo}
                                  </span>
                                </div>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
