import { useId } from 'react';

const Input = ({ 
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  disabled,
  error,
  id,
  ...props
}) => {
  const inputId = useId();
  const resolvedId = id || inputId;
  const errorId = `${resolvedId}-error`;

  return (
    <div className="input-group">
      {label && <label className="input-label" htmlFor={resolvedId}>{label}</label>}
      <input
        id={resolvedId}
        type={type}
        placeholder={placeholder}
        value={value}
        onChange={onChange}
        disabled={disabled}
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? errorId : undefined}
        className={`input-input ${error ? 'input-error' : ''}`}
        {...props}
      />
      {error && <span id={errorId} className="input-error-message">{error}</span>}
    </div>
  );
};

export default Input;
