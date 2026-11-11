import { howItWorks } from "../lib/content";

// Styled HTML boxes, not an image. Text wraps on small screens and follows
// the light and dark theme. Content comes from src/lib/content.ts.

function Arrow() {
  return (
    <div aria-hidden="true" className="flex justify-center py-1 text-muted">
      <svg viewBox="0 0 12 20" className="h-5 w-3">
        <path d="M6 0v17M1.5 12.5L6 17l4.5-4.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    </div>
  );
}

function Tool({ name }: { name: string }) {
  return (
    <span className="rounded border border-line bg-sunken px-1.5 py-0.5 font-mono text-xs">
      {name}
    </span>
  );
}

export function ArchitectureDiagram() {
  const { pipeline, services } = howItWorks;
  const last = pipeline.length - 1;
  return (
    <div className="grid gap-6 rounded-xl border border-line bg-sunken/60 p-4 sm:p-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
      <div>
        <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
          Request pipeline
        </div>
        <ol>
          {pipeline.map((stage, i) => {
            const edge = i === 0 || i === last;
            return (
              <li key={stage.id}>
                <div
                  className={`rounded-lg border px-3.5 py-3 ${
                    edge ? "border-accent bg-surface" : "border-line bg-surface"
                  } ${"loop" in stage && stage.loop ? "border-dashed" : ""}`}
                >
                  <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span className="font-mono text-xs text-muted">{i + 1}</span>
                    <h3 className="text-sm font-semibold">{stage.title}</h3>
                    {"loop" in stage && stage.loop ? (
                      <span className="tone tone-warn rounded px-1.5 py-0.5 text-xs font-medium">
                        loop - max steps + timeout
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-sm text-muted">{stage.text}</p>
                  {stage.items.length > 0 ? (
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {stage.items.map((name) => (
                        <Tool key={name} name={name} />
                      ))}
                    </div>
                  ) : null}
                  {"uses" in stage && stage.uses ? (
                    <p className="mt-2 text-xs text-muted">
                      <span className="font-medium text-accent">uses</span> {stage.uses}
                    </p>
                  ) : null}
                </div>
                {i < last ? <Arrow /> : null}
              </li>
            );
          })}
        </ol>
      </div>

      <div>
        <div className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted">
          Services behind the pipeline
        </div>
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
          {services.map((svc) => (
            <li key={svc.title} className="rounded-lg border border-line bg-surface px-3.5 py-3">
              <h3 className="text-sm font-semibold">{svc.title}</h3>
              <p className="mt-1 text-sm text-muted">{svc.text}</p>
              {svc.items.length > 0 ? (
                <ol className="mt-2 space-y-1">
                  {svc.items.map((item, i) => (
                    <li key={item} className="flex items-start gap-1.5 font-mono text-xs">
                      <span aria-hidden="true" className="text-muted">
                        {svc.title === "Hybrid retrieval" && i > 0 ? "->" : "-"}
                      </span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ol>
              ) : null}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
