# typed: true
extend T::Sig

sig {returns(Integer)}
def main(name)
  puts "Hello, #{name}!"
  name.length
end
