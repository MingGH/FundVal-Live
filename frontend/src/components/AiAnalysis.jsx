import React, { useState, useEffect } from 'react';
import { Bot, Sparkles, AlertTriangle, TrendingUp, TrendingDown, RefreshCcw } from 'lucide-react';
import { api, getPrompts } from '../services/api';

export const AiAnalysis = ({ fund }) => {
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [prompts, setPrompts] = useState([]);
  const [selectedPromptId, setSelectedPromptId] = useState(null);

  useEffect(() => {
    loadPrompts();
  }, []);

  const loadPrompts = async () => {
    try {
      const data = await getPrompts();
      setPrompts(data);
      // Set default prompt as selected
      const defaultPrompt = data.find(p => p.is_default);
      if (defaultPrompt) {
        setSelectedPromptId(defaultPrompt.id);
      }
    } catch (error) {
      console.error('Load prompts failed', error);
    }
  };

  const handleAnalyze = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await api.post('/ai/analyze_fund', {
        fund_info: fund,
        prompt_id: selectedPromptId
      });
      setAnalysis(response.data);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || '分析请求失败，请稍后重试';
      setError(errorMsg);
    } finally {
      setLoading(false);
    }
  };

  const getRiskColor = (level) => {
    if (!level) return 'text-slate-500 bg-slate-100';
    if (level.includes('高')) return 'text-red-600 bg-red-50 border-red-100';
    if (level.includes('中')) return 'text-orange-600 bg-orange-50 border-orange-100';
    return 'text-green-600 bg-green-50 border-green-100';
  };

  if (!analysis && !loading) {
    return (
      <div className="bg-gradient-to-br from-indigo-50 to-white rounded-2xl p-6 shadow-sm border border-indigo-100 flex flex-col items-center justify-center text-center">
        <Bot className="w-12 h-12 text-indigo-600 mb-3" />
        <h3 className="text-lg font-bold text-slate-800 mb-2">AI 深度市场分析</h3>
        <p className="text-slate-500 text-sm mb-6 max-w-md">
          基于 Linus Torvalds 风格的硬核逻辑分析。
          融合历史走势、实时估值、市场舆情，拒绝模棱两可的废话。
        </p>

        {/* Prompt Selector */}
        {prompts.length > 0 && (
          <div className="w-full max-w-md mb-4">
            <label className="block text-sm font-medium text-slate-700 mb-2">
              选择分析风格
            </label>
            <select
              value={selectedPromptId || ''}
              onChange={(e) => setSelectedPromptId(e.target.value ? parseInt(e.target.value) : null)}
              className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-transparent bg-white"
            >
              {prompts.map(p => (
                <option key={p.id} value={p.id}>
                  {p.name} {p.is_default ? '(默认)' : ''}
                </option>
              ))}
            </select>
          </div>
        )}

        <button
          onClick={handleAnalyze}
          className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-full font-medium transition-all shadow-lg shadow-indigo-200 flex items-center gap-2"
        >
          <Sparkles className="w-4 h-4" /> 开始生成报告
        </button>
        {error && <p className="text-red-500 text-xs mt-4">{error}</p>}
      </div>
    );
  }

  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-slate-100 relative overflow-hidden">
      {/* Loading Overlay */}
      {loading && (
        <div className="absolute inset-0 bg-white/80 backdrop-blur-sm z-10 flex flex-col items-center justify-center">
          <RefreshCcw className="w-8 h-8 text-indigo-600 animate-spin mb-3" />
          <p className="text-indigo-600 font-medium animate-pulse">Linus 正在审视市场逻辑...</p>
        </div>
      )}

      {/* Header */}
      <div className="flex justify-between items-start mb-6 border-b border-slate-50 pb-4">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-100 p-2 rounded-lg">
            <Bot className="w-6 h-6 text-indigo-700" />
          </div>
          <div>
            <h3 className="font-bold text-slate-800">AI 分析报告</h3>
            <p className="text-xs text-slate-400 mt-0.5">
              生成时间: {analysis?.timestamp || '--:--'} · 
              <span className="ml-1 text-indigo-600 font-mono">Linus Mode</span>
            </p>
          </div>
        </div>
        
        {analysis?.indicators && (
            <div className="flex gap-2">
                <span className={`px-2.5 py-1 rounded text-xs font-bold border ${getRiskColor(analysis.risk_level)}`}>
                    风险: {analysis.risk_level || '评估中'}
                </span>
                <span className={`px-2.5 py-1 rounded text-xs font-bold border bg-slate-50 text-slate-600 border-slate-200`}>
                    位置: {analysis.indicators.status}
                </span>
            </div>
        )}
      </div>

      {/* Indicators Section */}
      {analysis?.indicators && (
        <div className="mb-6 bg-slate-50 rounded-xl p-4 text-xs text-slate-600 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-slate-400" />
            {analysis.indicators.desc}
        </div>
      )}

      {/* Main Content */}
      {analysis && (
        <div className="space-y-4">
          <div className="prose prose-sm max-w-none text-slate-700 leading-relaxed whitespace-pre-line">
            {analysis.analysis_report}
          </div>
          
          {/* Summary Box */}
          <div className="mt-6 p-4 bg-indigo-50 rounded-xl border border-indigo-100">
            <h4 className="text-indigo-900 font-bold text-sm mb-2 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4" /> 核心结论
            </h4>
            <p className="text-indigo-800 text-sm font-medium">
                {analysis.summary}
            </p>
          </div>
        </div>
      )}
      
      {!loading && analysis && (
        <div className="mt-6 flex justify-center">
            <button 
                onClick={handleAnalyze}
                className="text-slate-400 hover:text-indigo-600 text-xs flex items-center gap-1 transition-colors"
            >
                <RefreshCcw className="w-3 h-3" /> 重新分析
            </button>
        </div>
      )}
    </div>
  );
};
