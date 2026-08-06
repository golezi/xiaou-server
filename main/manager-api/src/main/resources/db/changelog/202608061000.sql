-- 新增 JetLinks 鱼缸设备控制插件配置。
-- 每条 provider_code 必须与服务端注册的 function 名称一致。

-- JetLinks 服务端内部参数，不下发到插件调用参数。
INSERT INTO `sys_params` (id, param_code, param_value, value_type, param_type, remark)
SELECT 503, 'JETLINKS_ENDPOINT', 'https://你的JetLinks服务地址', 'string', 1, 'JetLinks 服务地址'
WHERE NOT EXISTS (SELECT 1 FROM `sys_params` WHERE param_code = 'JETLINKS_ENDPOINT');

INSERT INTO `sys_params` (id, param_code, param_value, value_type, param_type, remark)
SELECT 504, 'JETLINKS_TOKEN', '你的JetLinks访问令牌', 'string', 1, 'JetLinks 访问令牌'
WHERE NOT EXISTS (SELECT 1 FROM `sys_params` WHERE param_code = 'JETLINKS_TOKEN');

INSERT INTO ai_model_provider (id, model_type, provider_code, name, fields,
                               sort, creator, create_date, updater, update_date)
SELECT 'SYSTEM_PLUGIN_JETLINKS_SET',
       'Plugin',
       'set_device_property',
       'JetLinks 设备属性控制',
       JSON_ARRAY(
               JSON_OBJECT(
                       'key', 'property_id',
                       'type', 'string',
                       'label', '属性 ID'
               ),
               JSON_OBJECT(
                       'key', 'value',
                       'type', 'string',
                       'label', '属性值'
               )
       ),
       90, 0, NOW(), 0, NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_model_provider WHERE id = 'SYSTEM_PLUGIN_JETLINKS_SET');

INSERT INTO ai_model_provider (id, model_type, provider_code, name, fields,
                               sort, creator, create_date, updater, update_date)
SELECT 'SYSTEM_PLUGIN_JETLINKS_GET',
       'Plugin',
       'get_device_properties',
       'JetLinks 设备状态查询',
       JSON_ARRAY(
               JSON_OBJECT(
                       'key', 'property_ids',
                       'type', 'array',
                       'label', '要查询的属性 ID 列表'
               )
       ),
       91, 0, NOW(), 0, NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_model_provider WHERE id = 'SYSTEM_PLUGIN_JETLINKS_GET');

INSERT INTO ai_model_provider (id, model_type, provider_code, name, fields,
                               sort, creator, create_date, updater, update_date)
SELECT 'SYSTEM_PLUGIN_JETLINKS_INVOKE',
       'Plugin',
       'invoke_device_function',
       'JetLinks 设备功能调用',
       JSON_ARRAY(
               JSON_OBJECT(
                       'key', 'function_id',
                       'type', 'string',
                       'label', '实际调用的 JetLinks 功能名称'
               ),
               JSON_OBJECT(
                       'key', 'params',
                       'type', 'object',
                       'label', '功能调用参数'
               )
       ),
       92, 0, NOW(), 0, NOW()
WHERE NOT EXISTS (SELECT 1 FROM ai_model_provider WHERE id = 'SYSTEM_PLUGIN_JETLINKS_INVOKE');
