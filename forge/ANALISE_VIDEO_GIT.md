# Análise do vídeo "curso relâmpago de git" (heliofilhou), 11/10/2026

**Fonte:** vídeo vertical de 2m55s, 11 etapas animadas + apresentador com legenda queimada.
**Método de extração:** a transcrição automática foi bloqueada pela rede (download de modelo: 403). Legendas e
telas lidas quadro a quadro (2 por segundo, mosaicos com carimbo de tempo). O OCR automático foi descartado
por ser ruído (legenda branca sobre camisa branca, efeito karaokê). Um número quase saiu errado: o primeiro
mosaico mostrava "4%", que era um quadro intermediário do contador animado; o valor final é **90%**.

## Transcrição (reconstituída)
Curso relâmpago de git. Git e GitHub não são a mesma coisa: git é um sistema de controle de versão; GitHub é
um site que hospeda repositórios git. Digamos que você criou um projeto novo. Você roda `git init`, e isso
transforma a pasta num repositório git, e o git começa a acompanhar o histórico desse projeto. Mas o git não
salva sozinho cada mudança que você faz. Existem três áreas que você precisa entender: a pasta de trabalho, a
área de stage e o repositório. Digamos que você editou o `app.js`: essa mudança existe só na sua pasta de
trabalho. Se você rodar `git status`, o git te mostra que o arquivo mudou. Agora você roda `git add app.js`, e
isso leva a mudança pra área de stage. Pensa no stage dessa forma: "essas são exatamente as mudanças que eu
quero na próxima foto". E você roda o `git commit -m "adiciona a página de login"`, e o git cria o commit. Um
commit é basicamente uma foto salva do seu projeto naquele exato momento, e cada commit ganha um identificador
único. Imagine que você quer criar uma funcionalidade nova sem bagunçar o código principal: é nesse exato
momento que entram as branches. Você cria uma com `git switch -c nova-feature`, por exemplo, e agora tem uma
linha de desenvolvimento separada. Você faz mudanças, adiciona, commita; enquanto isso a branch main continua
intacta. [chamada para seguir o perfil] Quando a funcionalidade tá pronta, você volta com `git switch main` e
junta a branch com `git merge nova-feature`. O git tenta combinar as duas histórias sozinho. Se as duas
branches mexeram na mesma parte do mesmo arquivo, o git não sabe qual versão você quer: isso é um conflito de
merge. O git marca os trechos em conflito, você escolhe como o código final vai ficar e faz o commit do
resultado. Agora vamos colocar o GitHub nisso: você cria um repositório online e conecta ele ao seu
repositório local usando um remote; normalmente esse remote se chama `origin`. Quando você roda `git push`, os
seus commits locais sobem pro repositório remoto. Quando você roda `git pull`, o git baixa as mudanças novas do
remoto e junta na sua branch local. E o `git clone` simplesmente baixa um repositório que já existe, com todo o
histórico, pra sua máquina. Agora um comando que salva todo mundo o tempo todo: o `git log`. Ele mostra o
histórico dos commits, a árvore genealógica dos commits. E se você quebrar alguma coisa, o git tem várias
formas de voltar atrás: o `git restore` descarta a mudança nos arquivos; o `git revert` cria um commit novo que
desfaz um antigo; e o `git reset` pode mover a sua branch pra trás. É poderoso, mas também muito mais fácil de
usar errado. Então, se você lembrar só do fluxo básico, lembra disso: edita os arquivos, `git add`,
`git commit`, `git push`. Quando estiver trabalhando com outras pessoas, `git pull` antes de começar a mandar o
trabalho novo. Git parece complicado porque tem centenas de comandos, mas em 90% do tempo você tá fazendo uma
coisa só: criando um histórico limpo de como seu código mudou. [chamada: "comenta git que eu te mando uma
colinha com todos esses comandos e um material exclusivo"]

## Ratificação, alegação por alegação
| # | Alegação | Veredito | Nota |
|---|---|---|---|
| 1 | Git ≠ GitHub; git é controle de versão, GitHub hospeda repositórios | **VERDADEIRO** | GitHub também é rede de revisão (pull request), tarefas e CI |
| 2 | `git init` transforma a pasta em repositório e passa a acompanhar o histórico | **VERDADEIRO** | cria a pasta `.git`; só acompanha o que for adicionado |
| 3 | O git não salva sozinho | **VERDADEIRO** | |
| 4 | Três áreas: pasta de trabalho, stage, repositório | **VERDADEIRO** | é o modelo canônico (livro Pro Git: working tree, index, repository) |
| 5 | `git add` leva a mudança ao stage; stage = "o que eu quero na próxima foto" | **VERDADEIRO** | o add grava o conteúdo NAQUELE momento; editar de novo exige novo add |
| 6 | Commit = foto do projeto naquele momento | **VERDADEIRO** | o git guarda instantâneos, não diferenças |
| 7 | Cada commit ganha um identificador único | **INCOMPLETO no ponto mais importante** | o identificador é o HASH do conteúdo + do commit pai: mudar qualquer coisa do passado muda todos os identificadores seguintes. É isso que torna o histórico confiável, e o vídeo não diz |
| 8 | `git switch -c` cria branch; a main fica intacta | **VERDADEIRO** | `switch` existe desde o git 2.23 (2019); antes, `checkout -b` |
| 9 | Merge combina sozinho; conflito quando as duas mexeram na mesma parte do mesmo arquivo | **VERDADEIRO, simplificado** | também há conflito de "um apagou, o outro alterou" e de renomeação |
| 10 | Remote costuma se chamar `origin`; push sobe, pull baixa e junta, clone baixa tudo | **VERDADEIRO** | pull = fetch + merge (ou rebase, conforme configuração) |
| 11 | `git log` "salva todo mundo o tempo todo" | **EXAGERO** | mostra o histórico; quem salva de verdade depois de um `reset` errado é o `git reflog`, que o vídeo não cita |
| 12 | `restore` descarta, `revert` cria commit que desfaz, `reset` move a branch e é fácil de usar errado | **VERDADEIRO, com omissão perigosa** | o `restore` é o que apaga trabalho SEM volta (mudança nunca commitada não está no reflog); e `reset` em commit já enviado obriga reescrever o histórico de todos |
| 13 | Fluxo básico: editar, add, commit, push; pull antes, em equipe | **VERDADEIRO** | falta o `.gitignore`: o que NÃO deve entrar no add (senhas, chaves, dados) |
| 14 | "Git tem centenas de comandos" | **PLAUSÍVEL** | `git help -a` lista bem mais de 100, contando os internos |
| 15 | "Em 90% do tempo você está fazendo uma coisa só" | **SEM BASE** | número de efeito, sem fonte; o contador animado é retórica |
| 16 | "Comenta git que eu te mando uma colinha" | **MARKETING** | isca de engajamento (comentário em troca de mensagem) |

## Essência
O git é um **histórico em que só se acrescenta, endereçado por conteúdo**: cada registro carrega o hash do
anterior, a seleção do que entra é **explícita** (stage), linhas de trabalho são **isoladas** e só se juntam com
**decisão humana** quando há conflito, e a forma segura de corrigir o passado é **acrescentar** um registro que
desfaz (revert), nunca reescrever (reset). "Um histórico limpo de como o código mudou" é a frase central.

## Comparação com o COLLEGIUM
| Ideia do git | No COLLEGIUM | Situação |
|---|---|---|
| Commit = hash do conteúdo + pai | ANAIS: cada linha leva o hash da anterior (HMAC) + árvore de Merkle RFC 9162 | já existe, e vai além |
| Revert (corrigir acrescentando) × reset (reescrever) | O ANAIS só acrescenta; correção é registro novo (reabertura, recusa humana, errata datada no ADVERSARIAL_LOG) | já existe |
| Reset + force push reescreve o histórico de todos, e só percebe quem guardou o hash antigo | Prova de consistência: o cliente guarda a cabeça antiga e PROVA que a nova só a estende (`conferir-consistencia`) | já existe, e é exatamente o que o git não dá |
| Stage = escolha explícita do que entra | O plano é selado na abertura da tarefa; só entra o que o REGIMENTO permite | já existe |
| Merge com conflito: o git para e o humano decide | Valor repetido sem documento vai para a pilha do humano; nada é casado por palpite | já existe |
| `git add .` leva TUDO o que está na pasta | **Lacuna real:** rodar o produto dentro de uma cópia do repositório (que é PÚBLICO) e fazer `git add .` levava a chave privada e os dados do cliente para o próximo push | **corrigida: V-1** |

## O que foi implementado (V-1)
- `collegium/repositorio.py`: antes de gravar, detecta se o destino está dentro de um repositório git e fora
  do `.gitignore` (sem git instalado, considera publicável: falha fechada).
- `collegium gerar-chave`: **recusa** gravar chave privada nesse caso (chave não tem motivo legítimo para morar
  num repositório). `collegium conciliar`: **avisa** quando a pasta de resultado ou o ANAIS estão nesse caso
  (repositório privado pode ser escolha legítima).
- `.gitignore` do projeto: `*.priv`, `/demo/`, `/resultado/`, `/resultado_*/`, `anais*.jsonl*`. Achado antes do
  envio: meu 1º padrão (`/resultado*/`) também ignorava `resultados/`, a pasta da evidência publicada; o teste
  agora exige que evidência e código NUNCA fiquem ignorados.

## O que NÃO foi implementado, e por quê
- Ancorar a cabeça do ANAIS em commits do git: a prova de consistência já faz isso melhor; seria duplicação.
- Um "curso de git" no produto: o usuário do COLLEGIUM é contador, não programador; o produto não deve exigir git.
