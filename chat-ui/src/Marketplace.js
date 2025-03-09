import React, { useState } from 'react';
import { useNavigate } from "react-router-dom";

const Marketplace = () => {
  const [activeTab, setActiveTab] = useState(0);
  const [selectedModel, setSelectedModel] = useState(null);
  const [selectedDataProviders, setSelectedDataProviders] = useState([]);
  const navigate = useNavigate();

  const models = [
    { id: 'claude-3.5', name: 'Claude 3.5' },
    { id: 'claude-3.7', name: 'Claude 3.7' },
    { id: 'gemini-1.5', name: 'Gemini 1.5' },
    { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash' },
    { id: 'gemini-2.0-pro', name: 'Gemini 2.0 Pro' },
  ];

  const dataProviders = [
    { id: 'linkedin', name: 'LinkedIn Data' },
    { id: 'sanctions', name: 'Sanctions List' },
    { id: 'risk', name: 'Risk Rating' },
  ];

  const handleModelSelect = (modelId) => {
    setSelectedModel(modelId);
  };

  const handleDataProviderSelect = (providerId) => {
    setSelectedDataProviders(prev => {
      if (prev.includes(providerId)) {
        return prev.filter(id => id !== providerId);
      } else {
        return [...prev, providerId];
      }
    });
  };

  const handleSubmit = () => {
    navigate("/");
  };

  const handleNext = () => {
    setActiveTab(activeTab + 1);
  };

  return (
    <div className="flex flex-col h-screen bg-gray-100">
      <div className="flex flex-col h-full max-w-4xl mx-auto w-full shadow-lg bg-white">
        {/* Header */}
        <div className="bg-pink-600 text-white p-4">
          <h1 className="text-xl font-bold">AI Marketplace</h1>
          <p className="text-sm opacity-80">Select your model and data providers</p>
        </div>

        {/* Tabs */}
        <div className="flex">
          <button
            className={`flex-1 p-4 ${activeTab === 0 ? 'bg-gray-200' : ''} ${activeTab > 0 ? 'cursor-pointer' : 'cursor-default'}`}
            onClick={() => activeTab > 0 && setActiveTab(0)}
            disabled={activeTab < 1}
          >
            Splash
          </button>
          <button
            className={`flex-1 p-4 ${activeTab === 1 ? 'bg-gray-200' : ''} ${activeTab > 1 ? 'cursor-pointer' : 'cursor-default'}`}
            onClick={() => activeTab > 1 && setActiveTab(1)}
            disabled={activeTab < 2}
          >
            Model Selection
          </button>
          <button
            className={`flex-1 p-4 ${activeTab === 2 ? 'bg-gray-200' : ''}`}
            onClick={() => setActiveTab(2)}
            disabled={activeTab < 2}
          >
            Data Provider Selection
          </button>
        </div>

        {/* Tab Content */}
        <div className="p-4">
          {activeTab === 0 && (
            <div className="flex flex-col items-center">
              <h2 className="text-lg font-bold mb-2">Welcome to the AI Marketplace</h2>
              <img src="/AI_marketplace.jpeg" alt="AI Marketplace" className="max-w-md rounded-lg shadow-md mb-4" />
              <button
                className="bg-pink-600 text-white p-2 rounded"
                onClick={handleNext}
              >
                Next
              </button>
            </div>
          )}

          {activeTab === 1 && (
            <div>
              <h2 className="text-lg font-bold mb-2">Select a Model</h2>
              {models.map(model => (
                <div key={model.id} className="mb-2">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      name="model"
                      value={model.id}
                      onChange={() => handleModelSelect(model.id)}
                      className="mr-2"
                    />
                    {model.name}
                  </label>
                </div>
              ))}
              <button
                className="bg-pink-600 text-white p-2 rounded"
                onClick={handleNext}
              >
                Next
              </button>
            </div>
          )}

          {activeTab === 2 && (
            <div>
              <h2 className="text-lg font-bold mb-2">Select Data Providers</h2>
              {dataProviders.map(provider => (
                <div key={provider.id} className="mb-2">
                  <label className="flex items-center">
                    <input
                      type="checkbox"
                      value={provider.id}
                      onChange={() => handleDataProviderSelect(provider.id)}
                      className="mr-2"
                      checked={selectedDataProviders.includes(provider.id)}
                    />
                    {provider.name}
                  </label>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Submit Button */}
        {activeTab === 2 && (
          <div className="p-4">
            <button
              className="bg-pink-600 text-white p-2 rounded"
              onClick={handleSubmit}
            >
              Submit
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default Marketplace; 