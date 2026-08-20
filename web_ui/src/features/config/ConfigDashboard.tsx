import React, { useEffect, useState } from 'react';
import { ParameterInspection } from './ParameterInspection';
import { ConfigSearch } from './ConfigSearch';
import { ConfigValidation } from './ConfigValidation';
import { PolicyBrowser } from './PolicyBrowser';
import { CostStructure } from './CostStructure';

export const ConfigDashboard: React.FC = () => {
  const [categories, setCategories] = useState<string[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<string>('categories'); // 'categories', 'search', 'validation', 'policies', 'costs'
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    // We assume the API is available under /api/config. Adjust prefix if needed.
    fetch('/api/config/categories')
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch categories');
        return res.json();
      })
      .then((data) => {
        setCategories(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setError(err.message);
        setLoading(false);
      });
  }, []);

  const renderContent = () => {
    switch (activeTab) {
      case 'categories':
        return (
          <div style={{ display: 'flex', gap: 'var(--spacing-6)', height: '100%' }}>
            <div className="categories-list card" style={{ width: '300px', overflowY: 'auto' }}>
              <h2 style={{ marginBottom: 'var(--spacing-4)', fontSize: '1.25rem', fontWeight: 600 }}>Categories</h2>
              {loading && <div style={{ color: 'var(--color-neutral-500)' }}>Loading categories...</div>}
              {error && <div style={{ color: 'var(--color-error-text)' }}>{error}</div>}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2)' }}>
                {categories.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setSelectedCategory(cat)}
                    role="button"
                    tabIndex={0}
                    aria-label={`Select category ${cat}`}
                    style={{
                      textAlign: 'left',
                      padding: 'var(--spacing-3)',
                      borderRadius: 'var(--radius-md)',
                      border: '1px solid',
                      borderColor: selectedCategory === cat ? 'var(--color-primary-500)' : 'var(--border-default)',
                      backgroundColor: selectedCategory === cat ? 'var(--color-primary-50)' : 'var(--surface-default)',
                      color: selectedCategory === cat ? 'var(--color-primary-700)' : 'var(--color-neutral-700)',
                      cursor: 'pointer',
                      fontWeight: 500,
                      transition: 'all 0.2s',
                    }}
                  >
                    {cat}
                  </button>
                ))}
              </div>
            </div>
            <div className="category-details" style={{ flex: 1, overflowY: 'auto' }}>
              {selectedCategory ? (
                <ParameterInspection category={selectedCategory} />
              ) : (
                <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--color-neutral-500)' }}>
                  Select a configuration category to inspect its parameters.
                </div>
              )}
            </div>
          </div>
        );
      case 'search': return <ConfigSearch />;
      case 'validation': return <ConfigValidation />;
      case 'policies': return <PolicyBrowser />;
      case 'costs': return <CostStructure />;
      default: return null;
    }
  };

  const tabs = [
    { id: 'categories', label: 'Categories' },
    { id: 'search', label: 'Search' },
    { id: 'validation', label: 'Validation' },
    { id: 'policies', label: 'Policies' },
    { id: 'costs', label: 'Costs' },
  ];

  return (
    <div className="config-dashboard-container" style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-4)', height: '100%' }}>
      <div className="tabs" style={{ display: 'flex', gap: 'var(--spacing-2)', flexWrap: 'wrap' }}>
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            role="button"
            tabIndex={0}
            aria-label={`Navigate to ${tab.label}`}
            style={{
              padding: 'var(--spacing-2) var(--spacing-4)',
              borderRadius: 'var(--radius-md)',
              border: 'none',
              backgroundColor: activeTab === tab.id ? 'var(--color-primary-600)' : 'var(--surface-default)',
              color: activeTab === tab.id ? 'white' : 'var(--color-neutral-700)',
              cursor: 'pointer',
              fontWeight: 500,
              transition: 'all 0.2s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>
      <div style={{ flex: 1, overflow: 'hidden' }}>
        {renderContent()}
      </div>
    </div>
  );
};

export default ConfigDashboard;
