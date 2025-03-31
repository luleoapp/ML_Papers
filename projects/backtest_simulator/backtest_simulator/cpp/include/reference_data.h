#pragma once

#include <string>
#include <vector>
#include <map>
#include <unordered_map>
#include <any>
#include <variant>
#include <chrono>
#include <memory>

/**
 * @brief Value types that can be stored in reference data
 */
using ValueType = std::variant<
    bool,
    int,
    double,
    std::string,
    std::vector<bool>,
    std::vector<int>,
    std::vector<double>,
    std::vector<std::string>
>;

/**
 * @brief A single record in a reference data set
 */
using ReferenceRecord = std::unordered_map<std::string, ValueType>;

/**
 * @brief A collection of reference records
 */
using ReferenceDataSet = std::vector<ReferenceRecord>;

/**
 * @brief Manager for reference data in the C++ backtest engine
 */
class ReferenceDataManager {
public:
    ReferenceDataManager();
    ~ReferenceDataManager();

    /**
     * @brief Register a reference data set with the manager
     * @param name Name to identify this reference data set
     * @param data The reference data records
     * @return True if registration was successful
     */
    bool registerReferenceData(const std::string& name, const ReferenceDataSet& data);

    /**
     * @brief Get a reference data set by name
     * @param name Name of the reference data set
     * @return The reference data set, or empty vector if not found
     */
    const ReferenceDataSet& getReferenceData(const std::string& name) const;

    /**
     * @brief Check if a reference data set exists
     * @param name Name of the reference data set
     * @return True if the reference data set exists
     */
    bool hasReferenceData(const std::string& name) const;

    /**
     * @brief Get a list of all registered reference data set names
     * @return Vector of reference data set names
     */
    std::vector<std::string> getReferenceDataNames() const;

    /**
     * @brief Remove a reference data set
     * @param name Name of the reference data set to remove
     * @return True if the reference data set was removed
     */
    bool removeReferenceData(const std::string& name);

    /**
     * @brief Clear all reference data sets
     */
    void clearReferenceData();

    /**
     * @brief Find records in a reference data set that match a filter
     * @param name Name of the reference data set
     * @param field Field to filter on
     * @param value Value to match
     * @return Vector of matching records
     */
    ReferenceDataSet findRecords(const std::string& name, 
                               const std::string& field, 
                               const ValueType& value) const;

    /**
     * @brief Get a subset of a reference data set with only specific fields
     * @param name Name of the reference data set
     * @param fields Fields to include
     * @return Vector of records with only the specified fields
     */
    ReferenceDataSet getProjection(const std::string& name,
                                 const std::vector<std::string>& fields) const;

private:
    // Storage for reference data sets
    std::unordered_map<std::string, ReferenceDataSet> referenceDataSets_;
};

/**
 * @brief Runtime configuration for the backtest engine
 */
class EngineConfig {
public:
    EngineConfig();
    ~EngineConfig();

    /**
     * @brief Set a configuration parameter
     * @param key Parameter name
     * @param value Parameter value
     */
    void setParameter(const std::string& key, const ValueType& value);

    /**
     * @brief Get a configuration parameter
     * @param key Parameter name
     * @return Parameter value, or null variant if not found
     */
    ValueType getParameter(const std::string& key) const;

    /**
     * @brief Check if a parameter exists
     * @param key Parameter name
     * @return True if the parameter exists
     */
    bool hasParameter(const std::string& key) const;

    /**
     * @brief Get all parameter names
     * @return Vector of parameter names
     */
    std::vector<std::string> getParameterNames() const;

    /**
     * @brief Clear all parameters
     */
    void clearParameters();

private:
    // Storage for configuration parameters
    std::unordered_map<std::string, ValueType> parameters_;
};