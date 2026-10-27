import type { Recommendation } from "../../types/budgetFit";
import { RecommendationCard } from "./RecommendationCard";
import styles from "./RecommendationBoard.module.css";

interface RecommendationBoardProps {
  recommendations: Recommendation[];
  addedIds: Set<string>;
  onToggleAdd: (id: string) => void;
  pendingId?: string | null;
  addLabel?: string;
  addedLabel?: string;
}

export function RecommendationBoard({
  recommendations,
  addedIds,
  onToggleAdd,
  pendingId = null,
  addLabel,
  addedLabel,
}: RecommendationBoardProps) {
  return (
    <section className={styles.section}>
      <h2 className={styles.heading}>Recommendations</h2>
      <p className={styles.subheading}>
        {recommendations.length} options preserve required capabilities within budget.
      </p>
      <div className={styles.board}>
        {recommendations.map((recommendation) => (
          <RecommendationCard
            key={recommendation.id}
            recommendation={recommendation}
            added={addedIds.has(recommendation.id)}
            onToggleAdd={onToggleAdd}
            pending={pendingId === recommendation.id}
            addLabel={addLabel}
            addedLabel={addedLabel}
          />
        ))}
      </div>
    </section>
  );
}
