#include "reference_data.h"
#include <iostream>
#include <algorithm>

// Reference Data Manager implementation

ReferenceDataManager::ReferenceDataManager() {
    // Initialize reference data manager
}

ReferenceDataManager::~ReferenceDataManager() {
    // Cleanup
}

bool ReferenceDataManager::registerReferenceData(const std::string& name, const ReferenceDataSet& data) {
    // Store the reference data set
    referenceDataSets_[name] = data;
    return true;
}

const ReferenceDataSet& ReferenceDataManager::getReferenceData(const std::string& name) const {
    // Check if the reference data set exists
    auto it = referenceDataSets_.find(name);
    if (it != referenceDataSets_.end()) {
        return it->second;
    }
    
    // Return empty data set if not found
    static const ReferenceDataSet emptyDataSet;
    return emptyDataSet;
}

bool ReferenceDataManager::hasReferenceData(const std::string& name) const {
    return referenceDataSets_.find(name) != referenceDataSets_.end();
}

std::vector<std::string> ReferenceDataManager::getReferenceDataNames() const {
    std::vector<std::string> names;
    names.reserve(referenceDataSets_.size());
    
    for (const auto& pair : referenceDataSets_) {
        names.push_back(pair.first);
    }
    
    return names;
}

bool ReferenceDataManager::removeReferenceData(const std::string& name) {
    return referenceDataSets_.erase(name) > 0;
}

void ReferenceDataManager::clearReferenceData() {
    referenceDataSets_.clear();
}

ReferenceDataSet ReferenceDataManager::findRecords(
    const std::string& name, 
    const std::string& field, 
    const ValueType& value) const {
    
    // Get the reference data set
    const auto& dataSet = getReferenceData(name);
    if (dataSet.empty()) {
        return {};
    }
    
    // Filter records that match the field and value
    ReferenceDataSet result;
    
    for (const auto& record : dataSet) {
        auto it = record.find(field);
        if (it != record.end() && it->second == value) {
            result.push_back(record);
        }
    }
    
    return result;
}

ReferenceDataSet ReferenceDataManager::getProjection(
    const std::string& name,
    const std::vector<std::string>& fields) const {
    
    // Get the reference data set
    const auto& dataSet = getReferenceData(name);
    if (dataSet.empty() || fields.empty()) {
        return {};
    }
    
    // Create projected records with only the specified fields
    ReferenceDataSet result;
    result.reserve(dataSet.size());
    
    for (const auto& record : dataSet) {
        ReferenceRecord projectedRecord;
        
        for (const auto& field : fields) {
            auto it = record.find(field);
            if (it != record.end()) {
                projectedRecord[field] = it->second;
            }
        }
        
        if (!projectedRecord.empty()) {
            result.push_back(std::move(projectedRecord));
        }
    }
    
    return result;
}

// Engine Config implementation

EngineConfig::EngineConfig() {
    // Initialize engine configuration
}

EngineConfig::~EngineConfig() {
    // Cleanup
}

void EngineConfig::setParameter(const std::string& key, const ValueType& value) {
    parameters_[key] = value;
}

ValueType EngineConfig::getParameter(const std::string& key) const {
    auto it = parameters_.find(key);
    if (it != parameters_.end()) {
        return it->second;
    }
    
    // Return empty variant if not found
    return ValueType{};
}

bool EngineConfig::hasParameter(const std::string& key) const {
    return parameters_.find(key) != parameters_.end();
}

std::vector<std::string> EngineConfig::getParameterNames() const {
    std::vector<std::string> names;
    names.reserve(parameters_.size());
    
    for (const auto& pair : parameters_) {
        names.push_back(pair.first);
    }
    
    return names;
}

void EngineConfig::clearParameters() {
    parameters_.clear();
}