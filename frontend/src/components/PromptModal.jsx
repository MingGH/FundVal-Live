import React, { useState, useEffect } from 'react';
import { X, Save, AlertCircle, Info } from 'lucide-react';

export const PromptModal = ({ isOpen, onClose, onSave, prompt = null }) => {
  const [formData, setFormData] = useState({
    name: '',
    system_prompt: '',
    user_prompt: '',
    is_default: false
  });
  const [errors, setErrors] = useState({});
  const [saving, setSaving] = useState(false);

  const isEditMode = !!prompt;

  useEffect(() => {
    if (prompt) {
      setFormData({
        name: prompt.name || '',
        system_prompt: prompt.system_prompt || '',
        user_prompt: prompt.user_prompt || '',
        is_default: prompt.is_default || false
      });
    } else {
      setFormData({
        name: '',
        system_prompt: '',
        user_prompt: '',
        is_default: false
      });
    }
    setErrors({});
  }, [prompt, isOpen]);

  const availableVariables = [
    { key: 'fund_code', label: '基金代码' },
    { key: 'fund_name', label: '基金名称' },
    { key: 'fund_type', label: '基金类型' },
    { key: 'manager', label: '基金经理' },
    { key: 'nav', label: '最新净值' },
    { key: 'estimate', label: '实时估值' },
    { key: 'est_rate', label: '估值涨跌幅(%)' },
    { key: 'sharpe', label: '夏普比率' },
    { key: 'volatility', label: '年化波动率' },
    { key: 'max_drawdown', label: '最大回撤' },
    { key: 'annual_return', label: '年化收益' },
    { key: 'concentration', label: '持仓集中度(%)' },
    { key: 'holdings', label: '前10大持仓' },
    { key: 'history_summary', label: '历史走势摘要' }
  ];

  const validate = () => {
    const newErrors = {};

    if (!formData.name.trim()) {
      newErrors.name = '模板名称不能为空';
    } else if (formData.name.length > 100) {
      newErrors.name = '模板名称不能超过 100 字符';
    }

    if (!formData.system_prompt.trim()) {
      newErrors.system_prompt = '系统提示词不能为空';
    } else if (formData.system_prompt.length > 10000) {
      newErrors.system_prompt = '系统提示词不能超过 10000 字符';
    }

    if (!formData.user_prompt.trim()) {
      newErrors.user_prompt = '用户提示词不能为空';
    } else if (formData.user_prompt.length > 10000) {
      newErrors.user_prompt = '用户提示词不能超过 10000 字符';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSave = async () => {
    if (!validate()) return;

    setSaving(true);
    try {
      await onSave(formData);
      onClose();
    } catch (error) {
      setErrors({ submit: error.response?.data?.detail || '保存失败' });
    } finally {
      setSaving(false);
    }
  };

  const handleChange = (field, value) => {
    setFormData(prev => ({ ...prev, [field]: value }));
    if (errors[field]) {
      setErrors(prev => ({ ...prev, [field]: undefined }));
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-slate-200">
          <h2 className="text-2xl font-bold text-slate-800">
            {isEditMode ? '编辑提示词模板' : '新建提示词模板'}
          </h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 transition-colors"
          >
            <X className="w-6 h-6" />
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {/* Variable Hint */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-2">
              <Info className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
              <div className="flex-1">
                <p className="text-sm font-medium text-blue-900 mb-2">可用变量占位符</p>
                <div className="grid grid-cols-2 gap-2">
                  {availableVariables.map(v => (
                    <div key={v.key} className="flex items-center gap-2">
                      <code className="px-2 py-1 bg-white text-blue-700 text-xs rounded border border-blue-200 font-mono">
                        {`{${v.key}}`}
                      </code>
                      <span className="text-xs text-blue-800">{v.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              模板名称 <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => handleChange('name', e.target.value)}
              className={`w-full px-4 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent ${
                errors.name ? 'border-red-500' : 'border-slate-300'
              }`}
              placeholder="例如：Linus 风格"
              maxLength={100}
            />
            {errors.name && (
              <p className="mt-1 text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="w-4 h-4" /> {errors.name}
              </p>
            )}
          </div>

          {/* System Prompt */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              系统提示词 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={formData.system_prompt}
              onChange={(e) => handleChange('system_prompt', e.target.value)}
              className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm ${
                errors.system_prompt ? 'border-red-500' : 'border-slate-300'
              }`}
              placeholder="定义 AI 的角色和风格..."
              rows={8}
              maxLength={10000}
            />
            <div className="flex justify-between items-center mt-1">
              {errors.system_prompt ? (
                <p className="text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" /> {errors.system_prompt}
                </p>
              ) : (
                <p className="text-sm text-slate-500">
                  {formData.system_prompt.length} / 10000 字符
                </p>
              )}
            </div>
          </div>

          {/* User Prompt */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-2">
              用户提示词 <span className="text-red-500">*</span>
            </label>
            <textarea
              value={formData.user_prompt}
              onChange={(e) => handleChange('user_prompt', e.target.value)}
              className={`w-full px-4 py-3 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent font-mono text-sm ${
                errors.user_prompt ? 'border-red-500' : 'border-slate-300'
              }`}
              placeholder="使用 {fund_code}, {fund_name} 等变量..."
              rows={10}
              maxLength={10000}
            />
            <div className="flex justify-between items-center mt-1">
              {errors.user_prompt ? (
                <p className="text-sm text-red-600 flex items-center gap-1">
                  <AlertCircle className="w-4 h-4" /> {errors.user_prompt}
                </p>
              ) : (
                <p className="text-sm text-slate-500">
                  {formData.user_prompt.length} / 10000 字符
                </p>
              )}
            </div>
          </div>

          {/* Is Default */}
          <div className="flex items-center gap-3">
            <input
              type="checkbox"
              id="is_default"
              checked={formData.is_default}
              onChange={(e) => handleChange('is_default', e.target.checked)}
              className="w-4 h-4 text-blue-600 border-slate-300 rounded focus:ring-2 focus:ring-blue-500"
            />
            <label htmlFor="is_default" className="text-sm font-medium text-slate-700">
              设为默认模板（将取消其他模板的默认状态）
            </label>
          </div>

          {/* Submit Error */}
          {errors.submit && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-4">
              <p className="text-sm text-red-800 flex items-center gap-2">
                <AlertCircle className="w-5 h-5" /> {errors.submit}
              </p>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-200 bg-slate-50">
          <button
            onClick={onClose}
            className="px-6 py-2 text-slate-600 hover:text-slate-800 font-medium transition-colors"
            disabled={saving}
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex items-center gap-2 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
          >
            <Save className="w-4 h-4" />
            {saving ? '保存中...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  );
};
