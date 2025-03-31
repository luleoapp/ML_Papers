#pragma once

#include <string>
#include <vector>
#include <map>
#include <chrono>
#include <memory>

// Include reference data
#include "reference_data.h"

// Forward declarations
class OrderBook;
class TickProcessor;
class TradeMarker;

/**
 * @brief Main engine for backtesting
 */
class BacktestEngine {
public:
    BacktestEngine();
    ~BacktestEngine();

    /**
     * @brief Configure the engine with parameters
     * @param config Configuration parameters
     */
    void configure(const std::map<std::string, std::string>& config);

    /**
     * @brief Process a tick data file
     * @param file_path Path to the parquet file
     * @param date_str Date string in format YYYY-MM-DD
     * @param exchange Exchange name
     * @param universe List of symbols to process
     * @return Vector of result dictionaries
     */
    std::vector<std::map<std::string, std::string>> processFile(
        const std::string& file_path,
        const std::string& date_str,
        const std::string& exchange,
        const std::vector<std::string>& universe
    );
    
    /**
     * @brief Register reference data with the engine
     * @param name Name to identify this reference data
     * @param data The reference data
     * @return True if registration was successful
     */
    bool registerReferenceData(const std::string& name, const ReferenceDataSet& data);
    
    /**
     * @brief Get the reference data manager
     * @return Reference to the reference data manager
     */
    ReferenceDataManager& getReferenceDataManager() {
        return *reference_data_manager_;
    }
    
    /**
     * @brief Get the engine configuration
     * @return Reference to the engine configuration
     */
    EngineConfig& getEngineConfig() {
        return *engine_config_;
    }
    
    /**
     * @brief Set a runtime configuration parameter
     * @param key Parameter name
     * @param value Parameter value
     */
    void setConfigParameter(const std::string& key, const ValueType& value);
    
    /**
     * @brief Get a runtime configuration parameter
     * @param key Parameter name
     * @return Parameter value, or empty variant if not found
     */
    ValueType getConfigParameter(const std::string& key) const;

private:
    // Configuration parameters
    std::map<std::string, std::string> config_;

    // Processor components
    std::unique_ptr<OrderBook> order_book_;
    std::unique_ptr<TickProcessor> tick_processor_;
    std::unique_ptr<TradeMarker> trade_marker_;
    
    // Reference data management
    std::unique_ptr<ReferenceDataManager> reference_data_manager_;
    
    // Runtime configuration
    std::unique_ptr<EngineConfig> engine_config_;

    // Window tracking
    std::chrono::nanoseconds window_start_;
    std::chrono::nanoseconds window_end_;
    int max_window_size_secs_;
    int buffer_size_;
};
