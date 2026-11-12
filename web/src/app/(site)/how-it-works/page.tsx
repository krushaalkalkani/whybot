import type { Metadata } from "next";
import Link from "next/link";
import { ArchitectureDiagram } from "../../../components/ArchitectureDiagram";
import { PageIntro, SectionHeading } from "../../../components/ui";
import { howItWorks } from "../../../lib/content";

export const metadata: Metadata = {
  title: "How it works",
  description:
    "Architecture of WhyBot: planner, triage, investigate loop, hypothesis ranking, citation verifier and guardrails. Plus failure modes, limits and cost protection.",
};

export default function HowItWorksPage() {
  return (
    <div>
      <PageIntro title={howItWorks.heading}>{howItWorks.intro}</PageIntro>

      <section aria-labelledby="architecture">
        <SectionHeading id="architecture" note={howItWorks.diagramNote}>
          {howItWorks.diagramHeading}
        </SectionHeading>
        <ArchitectureDiagram />
      </section>

      <nav aria-label="On this page" className="mt-10 flex flex-wrap gap-2 text-sm">
        {howItWorks.sections.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className="rounded-md border border-line bg-surface px-2.5 py-1 text-muted hover:text-ink"
          >
            {s.title}
          </a>
        ))}
      </nav>

      <div className="mt-6 grid gap-x-10 gap-y-10 md:grid-cols-2">
        {howItWorks.sections.map((s) => (
          <section key={s.id} aria-labelledby={s.id}>
            <SectionHeading id={s.id} note={s.intro}>
              {s.title}
            </SectionHeading>
            <ul className="space-y-2">
              {s.bullets.map((b, i) => (
                <li key={i} className="border-t border-line pt-2 text-sm leading-relaxed">
                  {b}
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>

      <p className="mt-10 text-sm text-muted">
        See the numbers on the{" "}
        <Link href="/evals" className="text-accent underline underline-offset-2">
          Evals page
        </Link>{" "}
        or try a stored run on the{" "}
        <Link href="/demo" className="text-accent underline underline-offset-2">
          Demo page
        </Link>
        .
      </p>
    </div>
  );
}
