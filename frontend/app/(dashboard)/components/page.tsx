import { BreadcrumbNav } from '@/components/navigation/breadcrumb-nav';
import { ButtonShowcase } from '@/components/ui/button-showcase';

export default function ComponentsPage() {
  return (
    <>
      <BreadcrumbNav items={[{ title: 'Components' }]} />

      <main className="flex-1 space-y-6 bg-neutral-50 p-6">
        <div className="space-y-2">
          <h1 className="text-3xl font-bold text-neutral-900">
            Button Components
          </h1>
          <p className="text-lg text-neutral-600">
            Comprehensive button variant system for the ruleIQ platform
          </p>
        </div>

        <ButtonShowcase />
      </main>
    </>
  );
}
