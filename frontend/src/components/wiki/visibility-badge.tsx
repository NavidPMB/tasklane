import { Icon } from "@/components/ui/icon";
import { visibilityLabels, type Visibility } from "@/lib/wiki";

export function VisibilityBadge({ visibility }: { visibility: Visibility }) {
  return (
    <span className={`badge wiki-visibility wiki-visibility-${visibility}`}>
      <Icon
        name={
          visibility === "public"
            ? "globe"
            : visibility === "registered"
              ? "users"
              : "shield"
        }
        width={13}
        height={13}
      />
      {visibilityLabels[visibility]}
    </span>
  );
}
