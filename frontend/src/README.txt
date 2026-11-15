GLITCHLAB_ Build 05G.4B — Human-Friendly Policy Builder

Copy into frontend/src/:
  App.tsx                    REPLACE (removes old duplicate Policy Vault in workspace-only mode)
  WorkspacePolicyVault.tsx   REPLACE
  workspace-policy-vault.css REPLACE

No changes needed to backend or Supabase. Keep the Build 05G.4A PostgreSQL API
running on localhost:8001. Keep your existing four-demo login.

In frontend folder:
  npm.cmd run build
  npm.cmd run dev

Test as Kabir: readable rule description, regex hidden under Advanced,
no create form, and no old duplicated Brand Knowledge Vault.
Test as Reyansh: simple wording builder, sample sentence preview; test
with fictional example 'guaranteed', but avoid creating test rules unless
intended, because saving writes permanently to Supabase.

Limits: simple preview detects a case-insensitive literal substring,
not token boundaries or full Python regex semantics; regex advanced mode
has no live browser preview. New rules go live immediately and do not
constitute a reviewed policy release or source-grounded claim verification.
