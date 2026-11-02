import { Link } from 'react-router-dom';

const Button = ({ 
  children, 
  variant = 'primary', 
  size = 'medium',
  asLink = false,
  to,
  onClick,
  disabled,
  block,
  loading,
  className,
  type = 'button',
  ...props
}) => {
  const handleClick = asLink ? undefined : onClick;

  const Component = asLink ? Link : 'button';

  return (
    <Component
      to={to}
      type={type}
      onClick={handleClick}
      disabled={disabled || loading}
      className={`btn btn-${variant} btn-${size} ${block ? 'btn-block' : ''} ${loading ? 'btn-loading' : ''} ${className || ''}`}
      {...props}
    >
      {loading ? (
        <>
          <span className="spinner spinner-sm" aria-hidden="true"></span>
          {children}
        </>
      ) : children}
    </Component>
  );
};

export default Button;
