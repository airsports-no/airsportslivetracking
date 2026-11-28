import React from 'react';
import { Calculator } from 'lucide-react';
import { ScoringExplanation } from '../../utils/taskScore';

interface ScoringExplanationCardProps {
    explanation: ScoringExplanation;
    /** Shown after the text, for example a link to the scorecard. */
    footer?: React.ReactNode;
    className?: string;
}

const Section: React.FC<{ title: string; children: React.ReactNode }> = ({ title, children }) => (
    <section className="mt-3">
        <h3 className="text-sm font-semibold mb-1">{title}</h3>
        {children}
    </section>
);

const List: React.FC<{ items: string[] }> = ({ items }) => (
    <ul className="list-disc pl-5 space-y-1 text-sm">
        {items.map(item => (
            <li key={item}>{item}</li>
        ))}
    </ul>
);

/**
 * "How this task is scored": the backend's plain-language explanation of the task (display/services/scoring_explanation.py),
 * in full. It is the same text for a CIMA task, where scores are scaled against the best pilot and can change until all
 * flights are finished, and for a legacy task, where penalty points are added up.
 */
const ScoringExplanationCard: React.FC<ScoringExplanationCardProps> = ({ explanation, footer, className = '' }) => {
    const quality = explanation.scoring_model === 'quality';
    const options = explanation.qmax.options;
    return (
        <div className={`card bg-base-100 border border-base-300 shadow-sm ${className}`} data-testid="scoring-explanation-card">
            <div className="card-body p-4">
                <h2 className="card-title text-base gap-2">
                    <Calculator size={18} aria-hidden="true" />
                    How this task is scored
                </h2>
                <p className="text-sm font-medium">{explanation.headline}</p>

                <Section title={quality ? 'What a pilot’s raw points are made of' : 'How the score is made'}>
                    <List items={explanation.raw_points} />
                </Section>

                {quality && (
                    <Section title="From raw points to the task score">
                        <p className="text-sm">{explanation.task_score}</p>
                    </Section>
                )}
                {explanation.relative_terms.length > 0 && (
                    <Section title="Always shared against the best pilot">
                        <List items={explanation.relative_terms} />
                    </Section>
                )}

                {explanation.percentage_penalties.length > 0 && (
                    <Section title="Percentage penalties">
                        <List items={explanation.percentage_penalties} />
                    </Section>
                )}

                {quality && (
                    <Section title="Can the score change after landing?">
                        <div
                            className={`alert text-sm py-2 ${explanation.provisional.depends_on_other_pilots ? 'alert-warning' : 'alert-info'}`}
                            data-testid="scoring-explanation-provisional"
                        >
                            <span>{explanation.provisional.text}</span>
                        </div>
                    </Section>
                )}

                {quality && options.length > 0 && (
                    <Section title="How the best score is determined">
                        <ul className="space-y-2 text-sm">
                            {options.map(option => (
                                <li
                                    key={option.value}
                                    className={`rounded-md border p-2 ${option.is_selected ? 'border-primary bg-primary/5' : 'border-base-300'}`}
                                >
                                    <span className="font-medium">{option.label}</span>
                                    {option.is_selected && <span className="badge badge-primary badge-sm ml-2">In use</span>}
                                    {option.is_default && <span className="badge badge-ghost badge-sm ml-2">The rules&rsquo; default</span>}
                                    <p className="mt-1">{option.description}</p>
                                </li>
                            ))}
                        </ul>
                    </Section>
                )}

                {footer && <div className="mt-3 text-sm">{footer}</div>}
            </div>
        </div>
    );
};

export default ScoringExplanationCard;
