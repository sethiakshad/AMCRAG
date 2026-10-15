# AMCRAG --- Adaptive Multimodal Corrective Retrieval-Augmented Generation

> **Central project specification and source of truth**
>
> This document describes the purpose, architecture, technical
> decisions, data flow, algorithms, evaluation plan, research
> foundations, and team ownership for AMCRAG. It is intended to give a
> teammate, reviewer, or AI assistant enough context to understand the
> project without relying on previous conversations.
>
> **Project name used in diagrams:** AMC-RAG / AMCRAG\
> **Full name:** Adaptive Multimodal Corrective Retrieval-Augmented
> Generation\
> **Primary domain:** Question answering over PDF and document
> collections\
> **Core idea:** Select appropriate retrieval paths for a query,
> retrieve text and visually rich document evidence, fuse and rerank
> candidates, assess evidence quality, correct poor retrieval when
> necessary, and generate an answer grounded in the selected evidence.

------------------------------------------------------------------------

## 1. Project at a Glance

AMCRAG is a document question-answering system designed for collections
of PDFs that may contain ordinary prose as well as tables, charts,
figures, diagrams, and complex page layouts.

A conventional text-only RAG system can retrieve relevant passages, but
it can struggle when: - the first retrieved passages are irrelevant or
incomplete; - exact names, identifiers, or technical terms matter; - key
information is represented visually rather than in extractable prose; -
a chart or table's layout carries meaning that plain text extraction
loses; - the system needs to detect weak evidence and retry retrieval
rather than immediately answer.

AMCRAG combines four ideas:

1.  **Adaptive retrieval:** analyze the query and choose one or more
    retrieval paths.
2.  **Hybrid retrieval:** use dense semantic search and sparse keyword
    search for text.
3.  **Multimodal document retrieval:** use ColPali to retrieve visually
    relevant PDF pages.
4.  **Corrective retrieval:** assess retrieved evidence and
    reformulate/retrieve again when it is insufficient.

The selected evidence is then assembled into a context for an
answer-generation LLM. The system returns an answer with source/page
references where those references are available.

### One-line description

> AMCRAG adaptively retrieves textual and visual evidence from
> documents, fuses and reranks the candidates, checks evidence quality,
> corrects weak retrieval, and generates a source-grounded answer.

### High-level pipeline

``` text
PDFs ──> Document Processing ──> Text Chunks / Keyword Index / Visual Page Index

User Query
   |
   v
Query Analysis
   |
   v
Adaptive Retrieval Selection
   |
   +------> Dense Search (BGE + Qdrant)
   |
   +------> Sparse Search (BM25)
   |
   +------> Visual Page Search (ColPali)
                    |
                    v
            Result Fusion (RRF)
                    |
                    v
             BGE Reranker
                    |
                    v
           T5-Large CRAG Evaluator
                    |
        +-----------+------------+
        |           |            |
     CORRECT     AMBIGUOUS     INCORRECT
        |           |            |
        |      Further check     v
        |                 Query reformulation
        |                       |
        |                       +----> Retrieval again
        v
  Context Builder
        |
        v
  Answer Generation LLM
        |
        v
  Answer + Source References
```

The diagram above is a conceptual flow. The exact policy for the
`AMBIGUOUS` branch must be explicitly configured in implementation; it
should not be assumed to behave identically to `CORRECT` or `INCORRECT`.

------------------------------------------------------------------------

## 2. Goals and Non-Goals

### 2.1 Goals

-   Accept user questions about an uploaded or indexed document
    collection.
-   Process PDFs into retrieval-ready textual and visual
    representations.
-   Support semantic text search, keyword search, and visual page
    search.
-   Choose retrieval methods based on query characteristics.
-   Combine results from multiple retrieval methods.
-   Improve candidate ordering with a cross-encoder reranker.
-   Assess retrieved evidence before relying on it for answer
    generation.
-   Retry retrieval when the evidence is judged inadequate.
-   Generate answers grounded in selected context.
-   Preserve source metadata so answers can point users back to
    documents/pages.
-   Evaluate retrieval, evidence assessment, answer quality, and latency
    separately.
-   Make the system modular enough that individual retrieval methods can
    be benchmarked and replaced.

### 2.2 Non-goals / boundaries

Unless later added explicitly, AMCRAG is not assumed to: - train a new
foundation model from scratch; - guarantee that every generated answer
is correct; - use a learned Adaptive-RAG router (the current design uses
a rule-based query classifier); - use Self-RAG reflection tokens as its
correction mechanism; - treat the offline RAG evaluation framework as a
runtime module; - require OCR as the visual retrieval mechanism for
ColPali; - require microservices; the design can be implemented as a
modular application; - treat a successful retrieval score as proof that
a generated answer is factually correct.

### 2.3 Success criteria

The project should demonstrate, with repeatable experiments, whether its
components help: - text retrieval quality; - retrieval of visually
grounded PDF pages; - ranking quality after reranking; - recovery from
poor initial retrieval; - answer correctness and faithfulness; -
end-to-end latency and resource use.

The project should report measured results rather than inventing or
assuming improvements.

------------------------------------------------------------------------

## 3. Terminology

  -----------------------------------------------------------------------
  Term                                Meaning in AMCRAG
  ----------------------------------- -----------------------------------
  RAG                                 Retrieval-Augmented Generation:
                                      retrieve evidence, then generate an
                                      answer conditioned on it.

  Dense retrieval                     Semantic retrieval using vector
                                      representations of text.

  Sparse retrieval                    Term-based retrieval, implemented
                                      with BM25.

  Hybrid retrieval                    Combining multiple retrieval
                                      signals, here dense and sparse text
                                      retrieval and, where selected,
                                      visual retrieval.

  Visual retrieval                    Finding relevant PDF pages from
                                      their visual/document-page
                                      representations.

  Adaptive retrieval                  Selecting which retrieval path or
                                      combination of paths to run based
                                      on query characteristics.

  RRF                                 Reciprocal Rank Fusion, a
                                      rank-based method for merging
                                      result lists.

  Reranker                            A model that scores query-candidate
                                      pairs and reorders an existing
                                      candidate set.

  Evidence evaluator                  A component that assesses whether
                                      retrieved evidence is suitable for
                                      answering the query.

  CRAG                                Corrective Retrieval-Augmented
                                      Generation; evaluates retrieval
                                      quality and triggers corrective
                                      actions when needed.

  Context builder                     Creates the bounded, structured
                                      evidence package passed to the
                                      answer-generation model.

  Runtime evaluation                  A decision made while serving a
                                      query, such as whether to correct
                                      retrieval.

  Offline RAG evaluation              Experiments across a test dataset
                                      to measure system performance.
                                      These are distinct from runtime
                                      decisions.
  -----------------------------------------------------------------------

------------------------------------------------------------------------

## 4. System Architecture

The system is organized into two primary pipelines:

1.  **Document Processing Pipeline** --- prepares a document collection
    for retrieval.
2.  **Query Processing Pipeline** --- handles a question, retrieves
    evidence, checks it, and produces an answer.

An additional **offline Evaluation Pipeline** measures performance
across test questions. It is not a runtime step in the user's request
path.

### 4.1 Document Processing Pipeline

``` text
User uploads PDF
      |
      v
React UI
      |
      v
FastAPI upload endpoint
      |
      v
Document ingestion and processing
      |
      +--> PyMuPDF / Docling extraction
      |
      +--> Text chunks + metadata
      |        |
      |        +--> BGE embeddings --> Qdrant
      |        |
      |        +--> BM25 corpus/index
      |
      +--> PDF pages / page images
               |
               +--> ColPali page representations/index

Persistent artifacts:
- Qdrant vector collection
- BM25 index/corpus
- ColPali page index
- document/page/chunk metadata
```

#### Responsibilities

1.  Validate and register the uploaded document.
2.  Extract text, page boundaries, and useful structural information.
3.  Chunk extracted text for text retrieval.
4.  Attach metadata to every chunk, including document identity and page
    number where possible.
5.  Prepare text chunks for embedding and keyword indexing.
6.  Prepare PDF pages for ColPali indexing.
7.  Store or persist the resulting representations and their source
    mappings.
8.  Track processing failures so a partially processed document is not
    silently treated as fully indexed.

#### Document processing tools

-   **PyMuPDF:** PDF parsing, text extraction, page-level access, and
    page rendering where needed.
-   **Docling:** document conversion and structure-aware extraction,
    particularly useful for structured content and tables.
-   **LangChain Text Splitters:** split extracted text into
    retrieval-sized chunks.

The exact division of extraction responsibilities between PyMuPDF and
Docling should be implemented consistently. Avoid accidentally indexing
duplicate copies of the same text if both extractors process the same
content.

#### Chunk metadata

Each chunk should preserve enough metadata to trace retrieved text back
to its source. A conceptual record:

``` json
{
  "document_id": "doc_001",
  "chunk_id": "doc_001_chunk_0042",
  "page_start": 7,
  "page_end": 8,
  "text": "Extracted chunk text...",
  "source_filename": "example.pdf"
}
```

This is an illustrative data contract, not a claim that the current
implementation already uses these exact field names.

#### Page metadata

A conceptual visual-page record:

``` json
{
  "document_id": "doc_001",
  "page_number": 7,
  "source_filename": "example.pdf",
  "page_image_reference": "managed-page-reference"
}
```

The actual image bytes, embeddings, and index identifiers should be
stored according to the selected ColPali implementation. Avoid placing
large page-image payloads directly into ordinary metadata records.

### 4.2 Knowledge Stores

AMCRAG uses three specialized indexes/stores because each supports a
different retrieval signal.

#### A. Qdrant Vector Database

**Purpose:** store and search dense embeddings of text chunks.

-   Embedding model: `BAAI/bge-base-en-v1.5`
-   Input: text chunks
-   Stored representation: dense embedding vectors plus metadata
-   Query operation: embed the query and search for nearby vectors

Best suited for conceptual or semantically phrased questions where the
query wording differs from the document wording.

Example:

-   Query: "How does the model learn relationships between words?"
-   A relevant chunk may discuss self-attention without using the exact
    wording of the question.

#### B. BM25 Index

**Purpose:** sparse, term-based retrieval.

-   Implementation: `rank-bm25` (BM25Okapi or the selected BM25 variant)
-   Input: tokenized document chunks
-   Stored information: corpus terms and statistics used by the BM25
    scoring algorithm
-   Query operation: score documents based on query-term matches and
    term statistics

Best suited for exact technical terms, model names, identifiers,
acronyms, and values that may be important to match lexically.

**BM25 stands for "Best Matching 25."** The number is part of the
algorithm's name; it is not the number of results returned.

`rank-bm25` is an in-process Python implementation. It does not
automatically provide a persistent, standalone database service. The
project must deliberately persist or rebuild its index and keep its
corpus IDs aligned with the document metadata.

#### C. ColPali Page Index

**Purpose:** retrieve visually relevant PDF pages.

-   Model family: ColPali
-   Input: rendered PDF pages and a text query
-   Stored representation: visual/multivector page representations
    supported by the selected implementation
-   Query operation: compare query representations with indexed page
    representations using the model's retrieval/scoring method

Useful when evidence is carried by: - charts and plots; - tables whose
row/column relationships matter; - figures and diagrams; - page
layout; - mixed text and visual elements.

ColPali is not simply a third text embedding model. It uses a visual
document representation, which is why it can complement text-based
retrieval.

**OCR distinction:** OCR is not required to make ColPali perform visual
page retrieval. Text extraction remains important for the BGE/BM25 paths
and for producing readable context and citations. If OCR is added for
another use case, it should be treated as a separate text-extraction
component rather than a prerequisite for ColPali.

### 4.3 Query Processing Pipeline

``` text
User question
     |
     v
Query Analysis (rule-based)
     |
     v
Adaptive Retrieval Selection
     |
     +--> Dense search: BGE + Qdrant
     |
     +--> Sparse search: BM25
     |
     +--> Visual search: ColPali
                 |
                 v
          Result integration/fusion
                 |
                 v
             BGE Reranker
                 |
                 v
          T5-Large CRAG Evaluator
                 |
                 v
        Evidence-quality decision
                 |
       +---------+----------+
       |         |          |
    Correct   Ambiguous   Incorrect
       |         |          |
       |    configured      v
       |    policy     Reformulate query
       |                    |
       |                    +--> Adaptive Retrieval
       v
  Context Builder
       |
       v
  Answer Generation LLM
       |
       v
  Final answer + source references
```

### 4.4 Query Analysis and Adaptive Retrieval

The current design uses a **rule-based query classifier**, not a learned
routing model.

It examines query cues and selects one or more retrieval paths. Example
rules:

  -----------------------------------------------------------------------
  Query characteristics               Likely retrieval path
  ----------------------------------- -----------------------------------
  Conceptual or paraphrased question  Dense BGE retrieval

  Exact acronym, identifier, model    BM25; dense retrieval may also be
  name, technical phrase, or literal  useful
  value                               

  Explicit question about a chart,    ColPali
  figure, table, diagram, or visual   
  comparison                          

  Query requiring both an exact       Dense + BM25
  phrase and surrounding conceptual   
  context                             

  Complex question involving text and Multiple retrieval paths, followed
  visual evidence                     by fusion
  -----------------------------------------------------------------------

These are starting rules, not infallible classifications. A query can
contain a word such as "table" while still needing text retrieval. The
classifier should support multiple paths when appropriate and should be
evaluated on a labelled set of representative questions.

The key definition:

> Adaptive retrieval decides which retrieval method(s) to run. It does
> not, by itself, prove that the returned evidence is good.

### 4.5 Result Fusion: Reciprocal Rank Fusion (RRF)

Dense, sparse, and visual retrievers can return ranked lists with scores
that are not directly comparable. RRF combines rankings using rank
positions rather than requiring all raw scores to share the same scale.

A common RRF formula is:

\[ `\operatorname{RRF}`{=tex}(d)=`\sum`{=tex}\_{r
`\in `{=tex}R}`\frac{1}{k+\operatorname{rank}_r(d)}`{=tex} \]

Where: - (d) is a candidate; - (R) is the set of result lists; -
(`\operatorname{rank}`{=tex}\_r(d)) is the candidate's rank in list
(r); - (k) is a smoothing constant, often configured to a value such as
60.

The implementation should define: - how duplicate chunks/pages are
identified; - whether a text chunk and a visual page from the same
source are separate candidates; - how missing candidates are handled; -
how each retrieval path contributes; - how page/chunk IDs and source
metadata survive fusion.

**Ownership note:** Person 2 owns dense + BM25 retrieval and the initial
text-result fusion. Person 3 owns integration of ColPali candidates and
reranking. The team should maintain one agreed fusion interface rather
than building two competing RRF implementations.

### 4.6 BGE Reranker

Model: `BAAI/bge-reranker-base`.

**Role:** refine the ordering of an already retrieved candidate set.

A cross-encoder receives a query and a candidate passage together and
produces a relevance score. The system scores candidates and sorts them
accordingly.

``` text
Query + candidate 1 --> relevance score
Query + candidate 2 --> relevance score
Query + candidate 3 --> relevance score
                         |
                         v
                  Sort by score
```

It is different from `BAAI/bge-base-en-v1.5`:

  -----------------------------------------------------------------------
  Component               BGE embedding model     BGE reranker
  ----------------------- ----------------------- -----------------------
  Primary purpose         Retrieve candidates     Reorder retrieved
                          using vector similarity candidates

  Input                   Text to encode          Query + candidate pair
                          independently           

  Output                  Embedding vector        Relevance score

  Typical stage           Initial dense search    After candidate
                                                  retrieval/fusion
  -----------------------------------------------------------------------

A reranker is usually applied to a limited candidate set because scoring
every item in a large corpus with a cross-encoder would be expensive.

The reranker does **not** establish that the evidence is sufficient to
answer the question. That is the next component's responsibility.

### 4.7 Runtime CRAG Evidence Evaluator

The project plans to use a fine-tuned **T5-Large-based CRAG evaluator**.

The evaluator checks the retrieved evidence in relation to the user's
query. The intended system decision labels are:

-   **CORRECT:** evidence is sufficiently relevant for the configured
    policy to proceed.
-   **AMBIGUOUS:** evidence is uncertain, mixed, or incomplete; follow
    the explicitly configured additional-check policy.
-   **INCORRECT:** evidence is not suitable; trigger corrective
    retrieval where possible.

These labels are the system's decision categories. Their exact semantics
must match the selected evaluator checkpoint and its output
interpretation.

#### Evaluator versus reranker

-   **BGE Reranker:** "Which candidates should be placed first?"
-   **T5-Large CRAG evaluator:** "Is the retrieved evidence usable
    enough, or should the retrieval process be corrected?"

A high reranker score does not automatically mean the whole set covers
all facts needed to answer a multi-part query.

#### Checkpoint and fine-tuning

The project plan is to use a fine-tuned CRAG evaluator rather than
assume that an untouched general-purpose T5-Large model already
understands the required CRAG labels. Verify the chosen checkpoint, its
expected input/output format, license, model files, and inference code
before integration.

The base model name `google-t5/t5-large` refers to a general-purpose
T5-Large checkpoint. It is not, by itself, proof that a fine-tuned CRAG
evaluator is being used.

### 4.8 Corrective Retrieval Loop

When evidence is judged insufficient or incorrect, the correction
component should:

1.  Preserve the original user question.
2.  Inspect the query and retrieved evidence.
3.  Generate a reformulated or expanded retrieval query.
4.  Ask the adaptive retrieval controller to run the required retrieval
    path(s) again.
5.  Fuse and rerank the new candidates.
6.  Re-evaluate the evidence.
7.  Stop when the evidence is acceptable, the retry limit is reached, or
    no useful progress is made.

Illustrative example:

``` text
Question: "Which figure compares the models' accuracy?"

Initial retrieval:
- Introduction page
- Related-work page

Evaluator:
- Evidence does not contain the requested comparison.

Correction query:
- "model accuracy comparison figure results"

Second retrieval:
- A page containing the accuracy chart

Evaluator:
- Reassess the new evidence.
```

The example illustrates the intended mechanism; it does not guarantee
that a second attempt will succeed.

#### Stopping and failure behavior

The implementation must define: - maximum correction attempts; - what
happens when every attempt is judged insufficient; - what happens if the
evaluator fails or times out; - whether `AMBIGUOUS` triggers another
search or allows a qualified answer; - how the original question is
preserved during reformulation; - how to avoid cycling through nearly
identical queries.

If evidence remains inadequate, the safer behavior is to state that the
source collection did not provide enough evidence rather than invent a
confident answer.

### 4.9 Context Builder

The context builder receives accepted evidence and creates a bounded,
structured input for the answer-generation model.

It can combine: - relevant text chunks; - source page numbers; -
document identifiers and filenames; - relevant visual pages and their
references; - extracted table content where available; - retrieval
provenance and scores if useful.

It should: - deduplicate overlapping text; - preserve document/page
citations; - keep evidence associated with the correct source; - respect
the LLM's context limit; - distinguish extracted text from page-image
evidence; - avoid including unverified, low-quality candidates merely to
fill the prompt.

A conceptual context record:

``` json
{
  "question": "What does the document report?",
  "evidence": [
    {
      "document_id": "doc_001",
      "page": 7,
      "type": "text_chunk",
      "content": "Relevant extracted passage..."
    },
    {
      "document_id": "doc_001",
      "page": 8,
      "type": "visual_page",
      "content_reference": "managed-page-reference"
    }
  ]
}
```

This is an illustrative interface. The exact implementation may use
typed Python objects or another internal representation.

### 4.10 Answer Generation

Candidate answer-generation models in the design are **Qwen, Llama, or
Mistral**. The final model/checkpoint should be selected and documented
before benchmarking; do not treat all three as simultaneously selected
unless the application actually supports model switching.

The generation model receives: - the original question; - the context
builder's accepted evidence; - instructions to answer from the
evidence; - source metadata needed for citations.

Desired behavior: - answer the question directly; - ground factual
claims in the supplied evidence; - cite source document/page where
possible; - distinguish missing evidence from known facts; - avoid
fabricating values, page references, or citations; - indicate
uncertainty when the evidence does not support a definite answer.

The generator is downstream of retrieval evaluation, but this does not
mean its answer is automatically correct. That is why offline
answer-quality evaluation is necessary.

------------------------------------------------------------------------

## 5. Fixed Technology Stack

The following is the project's planned stack. It should be updated when
a specific library, model checkpoint, or database choice is finalized.

  --------------------------------------------------------------------------
  Component               Selected technology /      Purpose
                          candidate                  
  ----------------------- -------------------------- -----------------------
  Frontend                React                      Upload documents,
                                                     submit questions,
                                                     display answers and
                                                     sources

  Language                Python 3.11+               Backend and retrieval
                                                     pipeline

  Backend API             FastAPI                    Upload/query endpoints
                                                     and orchestration

  PDF processing          PyMuPDF + Docling          Extract text, page data
                                                     and document structure

  Chunking                LangChain Text Splitters   Split text into
                                                     retrieval units

  Dense embeddings        `BAAI/bge-base-en-v1.5`    Semantic text
                                                     representations

  Sparse retrieval        BM25 using `rank-bm25`     Keyword/term-based
                                                     retrieval

  Vector store            Qdrant                     Store/search dense
                                                     vectors and metadata

  Result fusion           Reciprocal Rank Fusion     Combine ranked result
                          (RRF)                      lists

  Visual retrieval        ColPali                    Retrieve visually
                                                     relevant PDF pages

  Reranking               `BAAI/bge-reranker-base`   Score and reorder
                                                     retrieved candidates

  Query analysis          Rule-based query           Select retrieval
                          classifier                 path(s)

  CRAG evaluator          Fine-tuned T5-Large-based  Assess retrieved
                          evaluator                  evidence and guide
                                                     correction

  Correction              Query reformulation +      Recover from poor
                          re-retrieval               retrieval

  Context assembly        Custom Python context      Build evidence for
                          builder                    generation

  Answer generation       Qwen / Llama / Mistral     Generate the final
                          (choose and pin a          answer
                          checkpoint)                

  Metadata storage        SQLite or PostgreSQL       Persist document and
                          (final choice to be        system metadata
                          documented)                

  Containerization        Docker (optional for       Package runtime and
                          development, useful for    services
                          reproducible deployment)   

  Offline evaluation      Custom benchmark scripts;  Measure retrieval,
                          optional RAG evaluation    answer quality and
                          framework                  latency
  --------------------------------------------------------------------------

### 5.1 Version and configuration policy

The repository should pin and document: - Python version; - exact
package versions in the dependency lock file; - model IDs and checkpoint
revisions where feasible; - vector collection schema and distance
metric; - chunk size and overlap; - retrieval Top-K values; - RRF
constant and fusion policy; - reranker candidate count; - evaluator
label/threshold policy; - correction retry limit; - generation model,
decoding settings and context limit; - evaluation dataset version and
random seeds where applicable.

Do not write "latest" as a reproducibility strategy. A reproducible run
needs actual versions/configuration recorded.

### 5.2 Configuration and secrets

Use environment variables for environment-specific settings and secrets.
Example variable names:

``` dotenv
APP_ENV=development
API_HOST=0.0.0.0
API_PORT=8000

QDRANT_URL=http://localhost:6333
QDRANT_COLLECTION=amcrag_text_chunks

METADATA_DATABASE_URL=sqlite:///./amcrag.db

EMBEDDING_MODEL=BAAI/bge-base-en-v1.5
RERANKER_MODEL=BAAI/bge-reranker-base
CRAG_EVALUATOR_PATH=/models/crag-evaluator
GENERATION_MODEL=<chosen-model-id>

MAX_CORRECTION_ATTEMPTS=2
```

This is a template only. Actual configuration names should match the
code. Never commit secrets or private API keys. A `.env.example` should
contain placeholders, not real credentials.

------------------------------------------------------------------------

## 6. Runtime Evaluation vs Offline RAG Evaluation

This distinction is fundamental.

### 6.1 Runtime evaluator (Person 4)

The T5-Large-based CRAG evaluator runs as part of serving a question.

It answers:

> "Is the evidence retrieved for this question good enough to proceed,
> or should retrieval be corrected?"

Its output changes the runtime control flow.

### 6.2 Offline evaluation pipeline (Person 5 coordinates)

The evaluation pipeline runs AMCRAG on a fixed test dataset and measures
performance.

It answers:

> "Across a collection of questions, how well does AMCRAG retrieve
> evidence and produce answers compared with baselines?"

It is not a required extra step for every production user query.

### 6.3 Evaluation dataset

Create a versioned dataset with: - question ID; - question text; -
source document IDs; - relevant page/chunk identifiers; - reference
answer or required facts where available; - query category (conceptual,
exact term/value, visual, mixed, multi-hop); - modality/evidence type
required; - notes about ambiguity or multiple valid sources.

A starting dataset may contain 50--100 carefully checked questions for
development, then be expanded if time permits. The final size should be
chosen based on project resources and reported honestly.

Include: - questions answerable from prose; - questions requiring exact
terminology or values; - chart/table/figure questions; - questions
requiring both text and visual evidence; - unanswerable or
insufficient-evidence questions; - multi-part questions.

Avoid building a test set only from queries the system already answers
well. Keep the test set separate from examples used to tune routing
rules and thresholds.

### 6.4 Retrieval metrics

#### Recall@K

Measures whether the relevant evidence appears among the top K results.

\[ `\operatorname{Recall@K}`{=tex} =
`\frac{\text{relevant items retrieved in top K}}`{=tex}
{`\text{all relevant items}`{=tex}} \]

For document retrieval, define relevance at the appropriate
granularity: - chunk-level for text retrieval; - page-level for visual
retrieval; - layout-level only if layout regions are annotated.

#### Precision@K

Fraction of the top K results that are relevant.

\[ `\operatorname{Precision@K}`{=tex} =
`\frac{\text{relevant items in top K}}{K}`{=tex} \]

#### MRR

Mean Reciprocal Rank measures how early the first relevant result
appears.

\[ `\operatorname{MRR}`{=tex} =
`\frac{1}{N}`{=tex}`\sum`{=tex}\_{i=1}\^{N}`\frac{1}{\operatorname{rank}_i}`{=tex}
\]

Questions with no relevant result need a consistent convention
(typically reciprocal rank zero).

#### nDCG@K

Measures ranking quality while accounting for result position and, if
defined, graded relevance. Use a consistent relevance-judgment scale.

### 6.5 Generation and RAG metrics

Potential metrics: - **Answer correctness:** whether the answer matches
a reference answer or required facts. - **Faithfulness:** whether answer
claims are supported by the provided evidence. - **Context precision:**
how much of the retrieved context is relevant. - **Context recall:**
whether the context includes the evidence needed to answer.

RAGAS or another evaluation toolkit may help automate some measures, but
metric definitions, judge models, and reference data must be documented.
LLM-based judge scores are not objective ground truth and should not be
reported without their evaluation setup.

### 6.6 System metrics

Measure: - ingestion time per document; - query analysis time; -
per-retriever latency; - fusion and reranking latency; - evaluator
latency; - correction-loop latency and number of attempts; - end-to-end
latency; - model memory and token usage where relevant; - failure rate
and timeout rate.

### 6.7 Required comparison experiments

Use the same test questions and comparable settings across
configurations.

1.  **Dense-only vs BM25-only vs Dense + BM25**
2.  **Text-only retrieval vs text + ColPali**
3.  **Before vs after BGE reranking**
4.  **Without correction vs with CRAG correction**
5.  **Fixed retrieval vs adaptive retrieval**
6.  **Baseline RAG vs AMCRAG**
7.  **One retrieval attempt vs correction-enabled multi-attempt
    workflow**, where useful

Not every experiment needs every metric. Use retrieval metrics for
retrieval experiments, evaluator metrics for the evaluator, and
answer-quality/system metrics for end-to-end comparisons.

### 6.8 Fairness and reproducibility rules

-   Use the same test set across compared systems.
-   Document Top-K, chunking, model versions, prompts and thresholds.
-   Do not tune on the final test set and then report it as an untouched
    test result.
-   Report failed queries and latency, not only successful examples.
-   Report the exact baseline configuration.
-   Never invent accuracy, recall, latency, or improvement percentages.
-   Separate retrieval quality from final answer quality.

------------------------------------------------------------------------

## 7. Baselines and Research Gap

The project is motivated by limitations that different RAG approaches
address in different ways. Avoid claiming that one paper has every
limitation below; describe each method accurately.

### 7.1 Standard RAG

The foundational RAG approach combines a retriever with a generator. A
basic implementation may retrieve a fixed number of text passages and
pass them to the LLM.

Potential limitation of a simple baseline: - no dedicated
retrieval-quality correction step; - irrelevant passages may enter the
context; - text-only indexes can miss evidence that depends on visual
page structure.

These are limitations of the baseline configuration, not a claim that
every modern RAG system lacks filtering or multimodal retrieval.

### 7.2 Adaptive-RAG

Adaptive-RAG adapts the RAG strategy to query complexity. It is not
accurate to describe the paper as using the same process for every
query.

AMCRAG's rule-based adaptive selector has a different emphasis:
selecting among **dense text, sparse keyword, and visual page
retrieval** based on query characteristics. The exact implementation is
a project-specific routing policy and should not be presented as a
reproduction of the Adaptive-RAG paper.

Potential gap addressed by AMCRAG: - combine retrieval-path selection
with multimodal PDF page retrieval and a corrective evidence-assessment
loop.

### 7.3 CRAG

Corrective Retrieval-Augmented Generation introduces retrieval
evaluation and corrective actions when retrieved documents are not good
enough.

Do not claim CRAG does not correct retrieval; correction is its central
contribution.

AMCRAG's proposed extension is to combine corrective retrieval with
adaptive selection among dense, sparse and visual retrieval paths for
document collections containing visually rich pages.

### 7.4 Self-RAG

Self-RAG uses a model trained to emit reflection tokens to guide
retrieval and assess relevance, support, and usefulness. It is not the
same as the separate-evaluator CRAG design.

AMCRAG's current design follows a CRAG-style external evidence-evaluator
path; it does not claim to implement Self-RAG reflection-token training.

### 7.5 Proposed contribution

The intended AMCRAG contribution is the integration of: - rule-based
adaptive selection among retrieval paths; - dense semantic text
retrieval; - sparse keyword retrieval; - ColPali visual page
retrieval; - result fusion and BGE reranking; - CRAG-style evidence
evaluation and corrective re-retrieval; - grounded answer generation
with source references; - component-level and end-to-end evaluation.

This is a proposed engineering/research contribution. The strength and
novelty of the claim must be assessed against related work and supported
by experiments; combining known components alone does not automatically
establish research novelty.

------------------------------------------------------------------------

## 8. Research Foundations

The following papers are relevant foundations. They are not all
implementations of the same architecture.

### 8.1 Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks

-   Authors: Patrick Lewis et al.
-   Year: 2020
-   Contribution: foundational retrieval-augmented generation framework
    combining a neural retriever with a sequence generator.
-   Relevance: standard RAG baseline and motivation for grounding
    generation in external knowledge.

### 8.2 Adaptive-RAG: Learning to Adapt Retrieval-Augmented Large Language Models through Question Complexity

-   Authors: Soyeong Jeong, Jinheon Baek, Sukmin Cho, Sung Ju Hwang,
    Jong C. Park
-   Venue: NAACL 2024
-   Contribution: adapts the retrieval strategy based on query
    complexity.
-   Relevance: supports the principle that not every question should
    require the same retrieval workflow.

### 8.3 Corrective Retrieval Augmented Generation (CRAG)

-   Authors: Shi-Qi Yan, Jia-Chen Gu, Yun Zhu, Zhen-Hua Ling
-   arXiv: 2401.15884 (2024)
-   Contribution: evaluates retrieved-document quality and triggers
    corrective actions.
-   Relevance: basis for AMCRAG's runtime evidence evaluator and
    correction loop.
-   Implementation note: verify the official checkpoint's expected
    inputs/outputs and the exact evaluator integration rather than
    assuming a generic T5-Large checkpoint is equivalent.

### 8.4 ColPali: Efficient Document Retrieval with Vision Language Models

-   Authors: Manuel Faysse et al.
-   Venue: ICLR 2025
-   Contribution: visual document retrieval using page images and
    multi-vector representations.
-   Relevance: motivation for retrieving visually rich PDF pages without
    relying exclusively on extracted text.
-   Licensing note: check the license of both the ColPali adapter and
    its underlying vision-language backbone. Do not assume the adapter's
    license automatically governs the backbone.

### 8.5 MMDocIR: Benchmarking Multimodal Retrieval for Long Documents

-   Authors: Kuicai Dong et al.
-   Venue: EMNLP 2025
-   Contribution: benchmark for multimodal retrieval from long
    documents, including page-level and layout-level retrieval.
-   Relevance: supports evaluation of visual and long-document
    retrieval. Its retrieval metrics should not be misrepresented as a
    complete evaluation of the generated answer.
-   Common metrics: Recall@K; layout-level evaluation depends on the
    benchmark's region annotations and protocol.

### 8.6 VisDoM: Multi-Document QA with Visually Rich Elements Using Multimodal Retrieval-Augmented Generation

-   Authors: Manan Suri et al.
-   Venue: NAACL 2025
-   Contribution: multimodal retrieval-augmented QA over visually rich
    elements.
-   Relevance: related work for combining visual and textual evidence.

### Research-use caution

Before final submission, verify citations, author lists, venues, dates,
licenses, and any numeric claims directly against the paper or official
repository. The project should cite the sources it actually uses and
distinguish a paper's reported results from AMCRAG's own measured
results.

------------------------------------------------------------------------

## 9. Team Ownership and Interfaces

The five-person division is intended to reduce overlapping work. Every
person owns implementation and experiments for a distinct module.
Integration is shared through agreed interfaces.

### Person 1 --- Document Processing and Knowledge Base

**Owns:** - upload/ingestion processing; - PyMuPDF and Docling
extraction; - text chunking; - document/page/chunk metadata; - preparing
dense, BM25 and ColPali index inputs; - source/page mapping and
ingestion tests.

**Does not own:** query-time retrieval algorithms, adaptive routing,
reranking, CRAG decisions, or final generation.

**Deliverable:** given a PDF, produce traceable text chunks, metadata,
and page inputs that downstream retrieval modules can index.

### Person 2 --- Dense/Sparse Text Retrieval and Text Fusion

**Owns:** - BGE embeddings at query and indexing time; - Qdrant
collection/search; - BM25 index/search; - text result normalization and
IDs; - initial dense + BM25 RRF; - text retrieval benchmarks.

**Does not own:** PDF extraction, ColPali internals, final reranker,
CRAG evaluator, or query-routing policy.

**Deliverable:** query → dense results + sparse results → fused text
candidate list.

### Person 3 --- Visual Retrieval and Reranking

**Owns:** - ColPali page indexing/search; - visual page candidates; -
integration of ColPali results into the shared candidate/fusion
interface; - BGE Reranker; - visual retrieval and ranking experiments.

**Does not own:** initial text extraction, BGE/Qdrant or BM25 internals,
CRAG correction decisions.

**Deliverable:** relevant visual pages plus a relevance-ranked combined
candidate set.

**Shared boundary:** Person 2 owns the dense + BM25 fusion
implementation; Person 3 and Person 2 agree on a single extension point
for adding ColPali results. Do not implement two separate fusion
systems.

### Person 4 --- CRAG Evaluator and Corrective Retrieval

**Owns:** - selected fine-tuned T5-Large CRAG evaluator integration; -
evidence decision logic; - Correct/Ambiguous/Incorrect handling; - query
reformulation request; - retry limits and stopping behavior; -
correction-specific benchmarks.

**Does not own:** candidate ranking, adaptive routing rules,
answer-generation prompting, or offline end-to-end benchmark
orchestration.

**Deliverable:** reranked evidence → evidence decision → proceed or
request another retrieval attempt.

### Person 5 --- Adaptive Workflow, Generation, Integration and Offline Evaluation

**Owns:** - rule-based query analysis; - adaptive retrieval selection; -
pipeline orchestration through FastAPI; - context builder; - selected
answer-generation model integration; - React UI and API integration; -
final source/citation formatting; - end-to-end RAG evaluation framework
and aggregate results.

**Does not own:** independently reimplementing the retrievers or CRAG
evaluator.

**Deliverable:** integrated user-facing system plus reproducible
end-to-end benchmark.

### Team ownership rule

Each module owner supplies a working module, unit/integration tests,
documented configuration, and results for their component. Person 5
integrates through the agreed interfaces but does not silently take over
everyone else's implementation. The team reviews interface changes
together.

------------------------------------------------------------------------

## 10. Suggested Internal Interfaces

The codebase should define clear contracts so modules can be developed
in parallel. The following Python-like examples are illustrative, not
mandatory final class names.

### 10.1 Common retrieval candidate

``` python
from dataclasses import dataclass
from typing import Any, Literal

CandidateType = Literal["text_chunk", "visual_page"]

@dataclass
class RetrievalCandidate:
    candidate_id: str
    document_id: str
    source_filename: str
    page_start: int | None
    page_end: int | None
    candidate_type: CandidateType
    text: str | None
    page_reference: str | None
    retrieval_method: str
    retrieval_rank: int
    retrieval_score: float | None
    metadata: dict[str, Any]
```

Every retriever should return candidates in a compatible structure. If
the candidate is a visual page and no extracted text exists, `text` can
be absent while `page_reference` remains available.

### 10.2 Retrieval interface

``` python
def retrieve(
    query: str,
    top_k: int,
    filters: dict | None = None
) -> list[RetrievalCandidate]:
    ...
```

Specific modules can have their own internal APIs, but the orchestrator
should not need to understand their private index structures.

### 10.3 Reranking interface

``` python
def rerank(
    query: str,
    candidates: list[RetrievalCandidate],
    top_k: int
) -> list[RetrievalCandidate]:
    ...
```

The output should preserve candidate IDs and source metadata, while
adding or recording reranker scores.

### 10.4 CRAG decision interface

``` python
from typing import Literal
from dataclasses import dataclass

EvidenceLabel = Literal["CORRECT", "AMBIGUOUS", "INCORRECT"]

@dataclass
class EvidenceDecision:
    label: EvidenceLabel
    score: float | None
    explanation: str | None
    needs_correction: bool
```

This is a conceptual contract. If the official evaluator emits a scalar
score, map that score to labels using the checkpoint's intended
thresholds rather than inventing arbitrary thresholds without
validation.

### 10.5 Correction interface

``` python
def reformulate_query(
    original_query: str,
    candidates: list[RetrievalCandidate],
    decision: EvidenceDecision,
    attempt_number: int
) -> str:
    ...
```

The correction component requests another retrieval attempt; the
orchestrator runs it through the adaptive retrieval controller. This
keeps query correction separate from the execution of retrieval.

### 10.6 Context and answer interfaces

``` python
def build_context(
    query: str,
    accepted_candidates: list[RetrievalCandidate],
    token_budget: int
) -> dict:
    ...
```

``` python
def generate_answer(
    query: str,
    context: dict
) -> dict:
    ...
```

The answer output should include the answer text and structured source
references, not only a free-form string.

------------------------------------------------------------------------

## 11. Suggested Repository Layout

This is a proposed organization. Adjust it to the actual repository
rather than claiming all files already exist.

``` text
amcrag/
├── README.md
├── .env.example
├── .gitignore
├── pyproject.toml / requirements.txt / lock file
├── docker-compose.yml                 # optional deployment setup
├── frontend/
│   ├── package.json
│   └── src/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── api/
│   │   ├── config/
│   │   ├── schemas/
│   │   ├── ingestion/
│   │   │   ├── pdf_processing.py
│   │   │   ├── chunking.py
│   │   │   └── metadata.py
│   │   ├── indexing/
│   │   │   ├── qdrant_index.py
│   │   │   ├── bm25_index.py
│   │   │   └── colpali_index.py
│   │   ├── retrieval/
│   │   │   ├── dense.py
│   │   │   ├── sparse.py
│   │   │   ├── visual.py
│   │   │   ├── fusion.py
│   │   │   └── reranker.py
│   │   ├── adaptive/
│   │   │   └── query_classifier.py
│   │   ├── crag/
│   │   │   ├── evaluator.py
│   │   │   ├── decisions.py
│   │   │   └── correction.py
│   │   ├── generation/
│   │   │   ├── context_builder.py
│   │   │   └── answer_generator.py
│   │   └── services/
│   └── tests/
├── evaluation/
│   ├── datasets/
│   ├── retrieval_eval.py
│   ├── generation_eval.py
│   ├── system_eval.py
│   ├── baselines/
│   └── reports/
├── docs/
│   ├── architecture.md
│   ├── decisions.md
│   └── experiments.md
└── scripts/
    ├── ingest_documents.py
    └── run_benchmarks.py
```

Do not commit large datasets, private PDFs, secrets, model weights, or
generated index files unless the repository's storage policy explicitly
allows them. Document how authorized team members obtain required
assets.

------------------------------------------------------------------------

## 12. API Design (Proposed)

FastAPI is the backend API layer. The following endpoints are a
suggested contract, not a claim that these endpoints are already
implemented.

  ----------------------------------------------------------------------------
  Method                  Endpoint                     Purpose
  ----------------------- ---------------------------- -----------------------
  `POST`                  `/documents`                 Upload/register a
                                                       document and start
                                                       ingestion

  `GET`                   `/documents`                 List indexed documents

  `GET`                   `/documents/{document_id}`   Get processing/indexing
                                                       status

  `DELETE`                `/documents/{document_id}`   Remove a document and
                                                       its associated index
                                                       entries

  `POST`                  `/query`                     Submit a question and
                                                       receive an answer with
                                                       source references

  `GET`                   `/health`                    Basic service health
                                                       check
  ----------------------------------------------------------------------------

A query response should ideally contain: - answer text; - cited
sources/page references; - retrieval path(s) used; - whether correction
was triggered; - number of attempts; - latency breakdown, at least in
logs or debug mode.

Do not expose sensitive internal prompts or private document content in
logs by default.

------------------------------------------------------------------------

## 13. Testing Strategy

### Unit tests

-   PDF extraction and page numbering;
-   chunking boundaries and metadata propagation;
-   deterministic ID generation;
-   BGE embedding shape and empty-input handling;
-   Qdrant upsert/search behavior;
-   BM25 tokenization and result IDs;
-   RRF duplicate handling and ranking;
-   reranker ordering;
-   evaluator output parsing;
-   correction retry limits;
-   citation/source mapping.

### Integration tests

-   ingest one PDF and retrieve a known passage;
-   retrieve an exact identifier with BM25;
-   retrieve a conceptual answer with dense search;
-   retrieve a known chart/table page using ColPali;
-   fuse results and preserve page/source IDs;
-   trigger a CRAG correction when evidence is deliberately poor;
-   ensure retry limits prevent infinite loops;
-   generate an answer with valid citations;
-   verify graceful behavior when a model/index/service is unavailable.

### End-to-end tests

Run a small fixed set of representative questions through the complete
system: - prose question; - exact-term question; - chart/figure
question; - mixed text + visual question; - unanswerable question; -
question that requires a correction attempt.

Store input, configuration, output, retrieved evidence, latency, and
expected behavior so failures are reproducible.

------------------------------------------------------------------------

## 14. Error Handling and Reliability

The implementation should handle: - corrupted or password-protected
PDFs; - empty text extraction; - documents containing scanned pages; -
unsupported file types; - duplicate uploads; - index failures or partial
indexing; - unavailable Qdrant; - model download/load errors; - GPU/CPU
memory limits; - empty retrieval results; - evaluator timeouts or
invalid outputs; - failed query reformulation; - repeated unsuccessful
correction attempts; - answer-generation timeouts.

Recommended behavior: - represent ingestion status explicitly (pending,
processing, completed, failed); - do not expose partially indexed
documents as fully ready; - retain traceable error IDs in logs; - use
bounded retries; - preserve the original question; - return a clear
insufficient-evidence response if recovery fails; - never fabricate
citations or claim that a correction succeeded when it did not.

------------------------------------------------------------------------

## 15. Security, Privacy and Operational Considerations

-   Validate uploaded file type and size.
-   Use safe filenames and avoid trusting user-provided paths.
-   Keep API keys and database credentials outside source control.
-   Apply authorization if documents are private to users or groups.
-   Ensure deletion removes associated vectors, BM25 entries, visual
    index records and metadata.
-   Avoid logging full document text unless explicitly needed and
    appropriately protected.
-   Restrict access to local model files and uploaded documents as
    appropriate.
-   Do not expose raw filesystem paths to end users.
-   Document the licenses and usage terms of models and libraries used
    in deployment.

### Docker and environments

Docker is optional during development. A Python virtual environment and
dependency lock file may be sufficient for local development. Docker is
useful when the team needs to package the application and system
dependencies consistently, especially when running multiple services.
`.env` files handle configuration; lock files pin packages; Docker
packages a runtime environment. These solve different problems.

------------------------------------------------------------------------

## 16. Known Design Decisions and Caveats

1.  **Adaptive selector:** rule-based in the current design. Do not
    describe it as a trained routing model.
2.  **Three indexes:** Qdrant, BM25, and ColPali are separate because
    they represent/search different signals, not because every query
    must always use all three.
3.  **RRF ownership:** Person 2 owns dense + BM25 fusion; Person 3
    integrates ColPali through a shared fusion interface. Keep one
    canonical fusion implementation.
4.  **Reranker:** BGE reranks candidates; it does not replace the CRAG
    evaluator.
5.  **CRAG evaluator:** use a verified fine-tuned checkpoint and follow
    its expected input/output/threshold design. Vanilla T5-Large alone
    is not a ready-made CRAG evaluator.
6.  **Ambiguous branch:** define explicit behavior. It may require
    another retrieval attempt or permit a carefully qualified answer
    depending on evidence and policy.
7.  **Visual context:** ColPali returns visual page evidence. The
    generation model may not automatically understand an image if only a
    text prompt is sent; decide whether to pass page images to a
    compatible multimodal generator, use extracted/serialized visual
    information, or use another explicit visual-context strategy. Do not
    silently assume every text-only LLM can interpret a page image.
8.  **Model choice:** Qwen, Llama and Mistral are alternatives in the
    design. Pin one concrete model for reproducible experiments, unless
    multi-model comparison is a deliberate experiment.
9.  **Metadata database:** SQLite/PostgreSQL is an unresolved choice in
    the stack description. Choose one for the actual implementation and
    document why.
10. **Evaluation claims:** report measured results only. Distinguish
    results from the literature from AMCRAG's own benchmark.
11. **Research novelty:** the project is an integration of established
    ideas. Claims about novelty must be narrow, supported by
    related-work analysis, and evaluated experimentally.
12. **Architecture vs evaluation:** the runtime T5 evaluator belongs in
    the system architecture; the offline RAG evaluation framework
    belongs in the experimental methodology.
13. **Chunk/page identity:** text chunks and visual pages must preserve
    document and page provenance through fusion, reranking, correction,
    context construction and final citations.
14. **Correction limit:** correction must be bounded to avoid infinite
    loops and excessive latency.

------------------------------------------------------------------------

## 17. Implementation Status

This document records the **intended architecture and agreed design**,
not an assertion that every component is complete.

Maintain a real status checklist in the repository. Update it as code
and tests are merged.

-   [ ] React document-upload and query interface
-   [ ] FastAPI application and API schemas
-   [ ] PDF ingestion and processing
-   [ ] Chunking and metadata/page mapping
-   [ ] Qdrant dense index
-   [ ] BM25 index and persistence/rebuild strategy
-   [ ] ColPali page index and visual search
-   [ ] Rule-based query classifier
-   [ ] Dense + BM25 retrieval
-   [ ] ColPali retrieval integration
-   [ ] Single canonical RRF fusion implementation
-   [ ] BGE reranker
-   [ ] Verified fine-tuned T5-Large CRAG evaluator
-   [ ] Correct/Ambiguous/Incorrect decision policy
-   [ ] Query reformulation and bounded retry loop
-   [ ] Context builder and citation provenance
-   [ ] Selected answer-generation model
-   [ ] End-to-end query workflow
-   [ ] Versioned evaluation dataset
-   [ ] Retrieval benchmark
-   [ ] Reranker benchmark
-   [ ] CRAG correction benchmark
-   [ ] End-to-end RAG benchmark
-   [ ] Latency/resource measurements
-   [ ] Reproducible setup instructions
-   [ ] Final model/library licensing review

Do not mark an item complete until its implementation is integrated and
its expected behavior has been tested.

------------------------------------------------------------------------

## 18. Glossary / Viva Quick Reference

**Why three stores?**\
Qdrant supports dense semantic text search, BM25 supports term-based
keyword search, and ColPali supports visual PDF page retrieval.

**Why adaptive retrieval?**\
Different queries need different signals. Adaptive retrieval chooses the
path(s) to run instead of blindly using the same path for every query.

**Hybrid vs adaptive retrieval?**\
Hybrid combines multiple retrieval signals. Adaptive chooses which
signals to activate. A system can be both adaptive and hybrid.

**Why RRF?**\
It merges ranked lists from different retrievers without assuming their
raw scores are directly comparable.

**Why a reranker after retrieval?**\
Initial retrieval is optimized for efficient candidate discovery. A
cross-encoder reranker uses the query and candidate together to refine
ordering.

**Why CRAG after reranking?**\
Ranking the candidates does not guarantee that the evidence set is
sufficient. CRAG evaluates evidence quality and can trigger correction.

**CRAG vs Self-RAG?**\
CRAG uses a retrieval-evaluation/correction mechanism. Self-RAG uses a
model trained for self-reflection through reflection tokens and related
decisions.

**Runtime evaluator vs RAG evaluation?**\
The T5-based evaluator decides what to do for an individual query.
Offline RAG evaluation measures system performance over a dataset.

**Why ColPali?**\
Important evidence can be carried by page visuals and layout, not just
extracted text.

**Why keep page metadata?**\
It makes source tracing and answer citations possible and allows visual
pages to be associated with their originating documents.

**Does the system always retrieve with all three methods?**\
No. The query classifier can select one or more paths. Complex or
uncertain cases may activate multiple methods.

**What happens if correction fails?**\
Stop at the configured retry limit and return an honest
insufficient-evidence response rather than hallucinating an answer.

------------------------------------------------------------------------

## 19. Final Mental Model

Keep these roles separate:

``` text
PERSON / MODULE        CORE QUESTION

Document processing    What data can we extract and index?
Text retrieval         Which text chunks match the question?
Visual retrieval       Which PDF pages match visually?
Reranking              Which retrieved candidates should rank highest?
CRAG evaluator         Is the evidence good enough to proceed?
Correction             How should retrieval be retried if evidence is poor?
Adaptive controller    Which retrieval path(s) should run?
Context builder        Which evidence should be passed to generation?
Answer generator       What answer is supported by that evidence?
Offline evaluation     How well did the system perform across test questions?
```

The complete AMCRAG principle is:

> **Prepare the document once; select retrieval paths per query;
> retrieve textual and/or visual evidence; fuse and rerank candidates;
> assess evidence quality; correct poor retrieval within bounded limits;
> build traceable context; generate a grounded answer; and measure the
> entire pipeline using reproducible experiments.**

This is the central design contract for the project. Implementation
details may evolve, but any change should preserve the distinctions
above or document why the architecture is changing.
