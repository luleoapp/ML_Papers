#include <pybind11/pybind11.h>
#include <pybind11/stl.h>
#include <pybind11/chrono.h>
#include <pybind11/stl_bind.h>
#include "backtest_engine.h"
#include "reference_data.h"

namespace py = pybind11;

// Bind vectors for better performance with large arrays
PYBIND11_MAKE_OPAQUE(std::vector<bool>);
PYBIND11_MAKE_OPAQUE(std::vector<int>);
PYBIND11_MAKE_OPAQUE(std::vector<double>);
PYBIND11_MAKE_OPAQUE(std::vector<std::string>);
PYBIND11_MAKE_OPAQUE(ReferenceDataSet);

PYBIND11_MODULE(backtest_engine, m) {
    m.doc() = "C++ backtest engine for processing tick data";

    // Bind vector types
    py::bind_vector<std::vector<bool>>(m, "VectorBool");
    py::bind_vector<std::vector<int>>(m, "VectorInt");
    py::bind_vector<std::vector<double>>(m, "VectorDouble");
    py::bind_vector<std::vector<std::string>>(m, "VectorString");
    
    // Bind ValueType variant
    py::class_<ValueType>(m, "ValueType")
        .def(py::init<>())
        .def(py::init<bool>())
        .def(py::init<int>())
        .def(py::init<double>())
        .def(py::init<std::string>())
        .def(py::init<std::vector<bool>>())
        .def(py::init<std::vector<int>>())
        .def(py::init<std::vector<double>>())
        .def(py::init<std::vector<std::string>>());
        
    // Bind ReferenceRecord type (dict-like)
    py::class_<ReferenceRecord>(m, "ReferenceRecord")
        .def(py::init<>())
        .def("__getitem__", [](const ReferenceRecord& self, const std::string& key) {
            auto it = self.find(key);
            if (it != self.end()) {
                return it->second;
            }
            throw py::key_error("Key not found: " + key);
        })
        .def("__setitem__", [](ReferenceRecord& self, const std::string& key, const ValueType& value) {
            self[key] = value;
        })
        .def("__contains__", [](const ReferenceRecord& self, const std::string& key) {
            return self.find(key) != self.end();
        })
        .def("__len__", [](const ReferenceRecord& self) { return self.size(); })
        .def("keys", [](const ReferenceRecord& self) {
            std::vector<std::string> keys;
            keys.reserve(self.size());
            for (const auto& pair : self) {
                keys.push_back(pair.first);
            }
            return keys;
        });
    
    // Bind ReferenceDataSet type (vector of records)
    py::bind_vector<ReferenceDataSet>(m, "ReferenceDataSet");
    
    // Bind ReferenceDataManager
    py::class_<ReferenceDataManager>(m, "ReferenceDataManager")
        .def(py::init<>())
        .def("register_reference_data", &ReferenceDataManager::registerReferenceData,
             "Register a reference data set with the manager")
        .def("get_reference_data", &ReferenceDataManager::getReferenceData,
             "Get a reference data set by name")
        .def("has_reference_data", &ReferenceDataManager::hasReferenceData,
             "Check if a reference data set exists")
        .def("get_reference_data_names", &ReferenceDataManager::getReferenceDataNames,
             "Get a list of all registered reference data set names")
        .def("remove_reference_data", &ReferenceDataManager::removeReferenceData,
             "Remove a reference data set")
        .def("clear_reference_data", &ReferenceDataManager::clearReferenceData,
             "Clear all reference data sets")
        .def("find_records", &ReferenceDataManager::findRecords,
             "Find records in a reference data set that match a filter")
        .def("get_projection", &ReferenceDataManager::getProjection,
             "Get a subset of a reference data set with only specific fields");
             
    // Bind EngineConfig
    py::class_<EngineConfig>(m, "EngineConfig")
        .def(py::init<>())
        .def("set_parameter", &EngineConfig::setParameter,
             "Set a configuration parameter")
        .def("get_parameter", &EngineConfig::getParameter,
             "Get a configuration parameter")
        .def("has_parameter", &EngineConfig::hasParameter,
             "Check if a parameter exists")
        .def("get_parameter_names", &EngineConfig::getParameterNames,
             "Get all parameter names")
        .def("clear_parameters", &EngineConfig::clearParameters,
             "Clear all parameters");

    // Bind BacktestEngine
    py::class_<BacktestEngine>(m, "BacktestEngine")
        .def(py::init<>())
        .def("configure", &BacktestEngine::configure, 
             "Configure the engine with parameters")
        .def("process_file", &BacktestEngine::processFile,
             "Process a tick data file and return results",
             py::arg("file_path"), py::arg("date_str"), 
             py::arg("exchange"), py::arg("universe"))
        .def("register_reference_data", &BacktestEngine::registerReferenceData,
             "Register reference data with the engine")
        .def("get_reference_data_manager", &BacktestEngine::getReferenceDataManager,
             py::return_value_policy::reference_internal,
             "Get the reference data manager")
        .def("get_engine_config", &BacktestEngine::getEngineConfig,
             py::return_value_policy::reference_internal,
             "Get the engine configuration")
        .def("set_config_parameter", &BacktestEngine::setConfigParameter,
             "Set a runtime configuration parameter")
        .def("get_config_parameter", &BacktestEngine::getConfigParameter,
             "Get a runtime configuration parameter");
}
