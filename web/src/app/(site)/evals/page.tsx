import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Badge, Card, PageIntro, SectionHeading } from "../../../components/ui";
import { evals, metricDefs } from "../../../lib/content";
import { NOT_RUN, fmtDecimal, fmtInt, fmtMetric, fmtPercent, fmtText } from "../../../lib/format";
import { summary, systemsInGroup, type SplitResult } from "../../../lib/summary";

export const metadata: Metadata = {
  title: "Evals",
  description:
    "Benchmark results for WhyBot: baselines, ablations, retrieval recall, judge calibration, security tests and error analysis.",
};

function NotRun() {
  return (
    <p className="rounded-lg border border-dashed border-line px-4 py-5 font-mono text-sm text-muted">
      {NOT_RUN}
    </p>
  );
}

function Cell({ value }: { value: string }) {
  return (
    <td
      className={`whitespace-nowrap px-3 py-2 text-right font-mono text-sm tabular-nums ${
        value === NOT_RUN ? "text-muted" : ""
      }`}
    >
      {value}
    </td>
  );
}

function TableShell({ children }: { children: ReactNode }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line bg-surface">
      <table className="w-full border-collapse text-left">{children}</table>
    </div>
  );
}

function Th({ children, right = false, title }: { children: ReactNode; right?: boolean; title?: string }) {
  return (
    <th
      scope="col"
      title={title}
      className={`whitespace-nowrap border-b border-line bg-sunken px-3 py-2 text-xs font-semibold text-muted ${
        right ? "text-right" : "text-left"
      }`}
    >
      {children}
    </th>
  );
}

function RowHead({ children }: { children: ReactNode }) {
  return (
    <th
      scope="row"
      className="sticky left-0 max-w-[11rem] border-r border-line bg-surface px-3 py-2 text-left text-sm font-medium sm:max-w-none sm:whitespace-nowrap"
    >
      {children}
    </th>
  );
}

function HowToRead({ children }: { children: ReactNode }) {
  return (
    <p className="mt-2 max-w-3xl text-sm text-muted">
      <span className="font-medium text-ink">How to read this: </span>
      {children}
    </p>
  );
}

function SplitMeta({ split }: { split: SplitResult }) {
  return (
    <p className="mb-2 font-mono text-xs text-muted">
      n = {fmtInt(split.n)} - run date: {fmtText(split.run_date)}
    </p>
  );
}

function MetricsTable({ split, group }: { split: SplitResult | null | undefined; group: string }) {
  if (!split) return <NotRun />;
  const rows = systemsInGroup(split, group);
  if (rows.length === 0) return <NotRun />;
  return (
    <>
      <SplitMeta split={split} />
      <TableShell>
        <thead>
          <tr>
            <th
              scope="col"
              className="sticky left-0 border-b border-r border-line bg-sunken px-3 py-2 text-left text-xs font-semibold text-muted"
            >
              System
            </th>
            {metricDefs.map((m) => (
              <Th key={m.key} right title={m.definition}>
                {m.label}
              </Th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.system} className="border-t border-line first:border-t-0">
              <RowHead>{row.label ?? row.system}</RowHead>
              {metricDefs.map((m) => (
                <Cell
                  key={m.key}
                  value={
                    row.complete && row.metrics?.[m.key] == null ? "n/a" : fmtMetric(m.kind, row.metrics?.[m.key])
                  }
                />
              ))}
            </tr>
          ))}
        </tbody>
      </TableShell>
    </>
  );
}

export default function EvalsPage() {
  const dev = summary.splits?.dev ?? null;
  const test = summary.splits?.test ?? null;
  const ablationSplit = test ?? dev;
  const ablationName = test ? "test split" : dev ? "dev split" : null;
  const benchmark = summary.benchmark ?? {};
  const retrieval = summary.retrieval ?? null;
  const judge = summary.judge_calibration ?? null;
  const security = summary.security ?? null;
  const errors = summary.error_analysis ?? null;
  const t = evals.tables;

  return (
    <div>
      <PageIntro title={evals.heading}>{evals.intro}</PageIntro>

      <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
        <Card className="p-4">
          <h2 className="text-sm font-semibold">{evals.benchmarkHeading}</h2>
          <dl className="mt-3 grid grid-cols-3 gap-x-4 gap-y-3">
            {Object.entries(evals.benchmarkLabels).map(([key, label]) => {
              const v = benchmark[key];
              return (
                <div key={key}>
                  <dt className="text-xs text-muted">{label}</dt>
                  <dd className="font-mono text-sm">
                    {typeof v === "number" ? fmtInt(v) : fmtText(v)}
                  </dd>
                </div>
              );
            })}
          </dl>
        </Card>
        <Card className="p-4">
          <h2 className="text-sm font-semibold">{evals.modelsHeading}</h2>
          <dl className="mt-3 space-y-3">
            <div>
              <dt className="text-xs text-muted">Agent model</dt>
              <dd className="break-all font-mono text-sm">{fmtText(summary.models?.agent)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Judge model</dt>
              <dd className="break-all font-mono text-sm">{fmtText(summary.models?.judge)}</dd>
            </div>
            <div>
              <dt className="text-xs text-muted">Results generated</dt>
              <dd className="break-all font-mono text-sm">{fmtText(summary.generated_at)}</dd>
            </div>
          </dl>
        </Card>
      </div>

      <section className="mt-10" aria-labelledby="systems">
        <SectionHeading id="systems">{evals.systemsHeading}</SectionHeading>
        <ul className="grid gap-3 md:grid-cols-3">
          {evals.systems.map((s) => (
            <li key={s.label} className="rounded-lg border border-line bg-surface p-3.5">
              <div className="text-sm font-semibold">{s.label}</div>
              <p className="mt-1 text-sm text-muted">{s.text}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="mt-10" aria-labelledby="main-test">
        <SectionHeading id="main-test">{t.mainTest.title}</SectionHeading>
        <MetricsTable split={test} group="main" />
        <HowToRead>{t.mainTest.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="main-dev">
        <SectionHeading id="main-dev">{t.mainDev.title}</SectionHeading>
        <MetricsTable split={dev} group="main" />
        <HowToRead>{t.mainDev.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="ablation">
        <SectionHeading id="ablation">
          {t.ablation.title}
          {ablationName ? ` - ${ablationName}` : ""}
        </SectionHeading>
        <MetricsTable split={ablationSplit} group="ablation" />
        <HowToRead>{t.ablation.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="retrieval">
        <SectionHeading id="retrieval">{t.retrieval.title}</SectionHeading>
        {retrieval && retrieval.rows && retrieval.rows.length > 0 ? (
          <>
            <p className="mb-2 font-mono text-xs text-muted">
              split: {fmtText(retrieval.split)} - queries: {fmtInt(retrieval.n_queries)}
            </p>
            <TableShell>
              <thead>
                <tr>
                  <Th>Config</Th>
                  <Th right>Recall@10</Th>
                  <Th right>MRR</Th>
                </tr>
              </thead>
              <tbody>
                {retrieval.rows.map((row) => (
                  <tr key={row.config} className="border-t border-line first:border-t-0">
                    <RowHead>{row.config}</RowHead>
                    <Cell value={fmtPercent(row.recall_at_10)} />
                    <Cell value={fmtDecimal(row.mrr, 3)} />
                  </tr>
                ))}
              </tbody>
            </TableShell>
          </>
        ) : (
          <NotRun />
        )}
        <HowToRead>{t.retrieval.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="judge">
        <SectionHeading id="judge">{t.judge.title}</SectionHeading>
        {judge ? (
          <TableShell>
            <thead>
              <tr>
                <Th>Judge model</Th>
                <Th right>Sample size</Th>
                <Th right>Agreement</Th>
                <Th right>Cohen&apos;s kappa</Th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <RowHead>
                  <span className="font-mono">{fmtText(judge.judge_model)}</span>
                </RowHead>
                <Cell value={fmtInt(judge.n)} />
                <Cell value={fmtPercent(judge.agreement)} />
                <Cell value={fmtDecimal(judge.cohens_kappa, 2)} />
              </tr>
            </tbody>
          </TableShell>
        ) : (
          <NotRun />
        )}
        <HowToRead>{t.judge.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="security">
        <SectionHeading id="security">{t.security.title}</SectionHeading>
        {security ? (
          <>
            <p className="mb-2 font-mono text-xs text-muted">
              passed: {fmtInt(security.passed)} of {fmtInt(security.total)}
            </p>
            {security.tests && security.tests.length > 0 ? (
              <TableShell>
                <thead>
                  <tr>
                    <Th>Test</Th>
                    <Th>OWASP category</Th>
                    <Th right>Result</Th>
                  </tr>
                </thead>
                <tbody>
                  {security.tests.map((test) => (
                    <tr key={test.name} className="border-t border-line first:border-t-0">
                      <RowHead>{test.name}</RowHead>
                      <td className="px-3 py-2 font-mono text-sm">{fmtText(test.owasp)}</td>
                      <td className="px-3 py-2 text-right">
                        {test.passed === true ? (
                          <Badge tone="ok">passed</Badge>
                        ) : test.passed === false ? (
                          <Badge tone="bad">failed</Badge>
                        ) : (
                          <span className="font-mono text-sm text-muted">{NOT_RUN}</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </TableShell>
            ) : (
              <NotRun />
            )}
          </>
        ) : (
          <NotRun />
        )}
        <HowToRead>{t.security.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="errors">
        <SectionHeading id="errors">{t.errors.title}</SectionHeading>
        {errors && errors.length > 0 ? (
          <TableShell>
            <thead>
              <tr>
                <Th>Category</Th>
                <Th right>Count</Th>
                <Th>Example ids</Th>
                <Th>Fix</Th>
              </tr>
            </thead>
            <tbody>
              {errors.map((row) => (
                <tr key={row.category} className="border-t border-line align-top first:border-t-0">
                  <RowHead>{row.category}</RowHead>
                  <Cell value={fmtInt(row.count)} />
                  <td className="px-3 py-2 font-mono text-xs">
                    {row.example_ids && row.example_ids.length > 0
                      ? row.example_ids.join(", ")
                      : NOT_RUN}
                  </td>
                  <td className="min-w-[14rem] px-3 py-2 text-sm">{fmtText(row.fix)}</td>
                </tr>
              ))}
            </tbody>
          </TableShell>
        ) : (
          <NotRun />
        )}
        <HowToRead>{t.errors.how}</HowToRead>
      </section>

      <section className="mt-10" aria-labelledby="definitions">
        <SectionHeading id="definitions">{evals.definitionsHeading}</SectionHeading>
        <dl className="grid gap-x-8 gap-y-3 md:grid-cols-2">
          {metricDefs.map((m) => (
            <div key={m.key} className="border-t border-line pt-2.5">
              <dt className="text-sm font-semibold">
                {m.label} <span className="font-mono text-xs font-normal text-muted">{m.key}</span>
              </dt>
              <dd className="mt-0.5 text-sm text-muted">{m.definition}</dd>
            </div>
          ))}
        </dl>
      </section>
    </div>
  );
}
