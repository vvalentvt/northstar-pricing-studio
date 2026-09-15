import type { Recommendation } from "../types/budgetFit";
import { RecommendationCard } from "./RecommendationCard";
import styles from "./RecommendationBoard.module.css";

interface RecommendationBoardProps {
  recommendations: Recommendation[];
  addedIds: Set<string>;
  onToggleAdd: (id: string) => void;
}

export function RecommendationBoard({ recommendations, addedIds, onToggleAdd }: RecommendationBoardProps) {
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
          />
        ))}
      </div>
    </section>
  );
}
