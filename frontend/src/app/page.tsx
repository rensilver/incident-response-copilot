import { Workspace } from "../components/ui/workspace";
import { InvestigationWorkspace } from "../features/investigations/investigation-workspace";

export default function Page(): React.JSX.Element {
  return (
    <Workspace>
      <InvestigationWorkspace />
    </Workspace>
  );
}
